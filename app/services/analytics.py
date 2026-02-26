from collections import defaultdict
from statistics import median

# ── Monday.com status label mappings (actual values from the boards) ──
# Deals board statuses
DEAL_WON_STATUSES = {"won", "done"}
DEAL_LOST_STATUSES = {"dead"}
DEAL_ACTIVE_STATUSES = {"open", "working on it"}
DEAL_HOLD_STATUSES = {"on hold"}

# Work orders board statuses
WO_COMPLETED_STATUSES = {"completed", "done"}
WO_IN_PROGRESS_STATUSES = {"in progress", "working on it", "executed until current month"}
WO_NOT_STARTED_STATUSES = {"not started"}


# ── Helper functions ──

def _safe_float(value) -> float | None:
    """Safely convert a value to float, returning None on failure."""
    if value is None:
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def _get_deal_value(d: dict) -> float | None:
    """Extract deal value from a row (Monday.com column: 'Amount')."""
    raw = d.get("amount") or d.get("value") or d.get("deal_value")
    return _safe_float(raw)


def _get_status(d: dict) -> str:
    """Extract status from a row (Monday.com column: 'Status')."""
    return d.get("status") or d.get("stage") or "Unknown"


def _get_sector(d: dict) -> str:
    """Extract sector from a row (Monday.com column: 'Sector')."""
    return d.get("sector") or d.get("industry") or "Unknown"


# ── Deal Pipeline Analytics ──

def pipeline_metrics(deals: list[dict]) -> dict:
    """
    Compute pipeline-level metrics from the Deals board.
    
    Statuses: Open, Working on it, Won, Done, Dead, On Hold
    """
    values: list[float] = []
    stage_counts: dict[str, int] = defaultdict(int)
    active_values: list[float] = []

    for d in deals:
        status = _get_status(d)
        # Skip header rows that leaked through
        if status.lower() == "deal status":
            continue

        val = _get_deal_value(d)
        if val is not None:
            values.append(val)
            if status.lower() in DEAL_ACTIVE_STATUSES:
                active_values.append(val)

        stage_counts[status] += 1

    total = sum(values)
    count = len(values)

    return {
        "total_pipeline_value": round(total, 2),
        "active_pipeline_value": round(sum(active_values), 2),
        "deal_count": count,
        "avg_deal_size": round(total / count, 2) if count else 0,
        "median_deal_size": round(median(values), 2) if values else 0,
        "max_deal": round(max(values), 2) if values else 0,
        "min_deal": round(min(values), 2) if values else 0,
        "stage_breakdown": dict(stage_counts),
    }


def sector_metrics(deals: list[dict]) -> dict:
    """Compute per-sector aggregations from the Deals board."""
    sectors: dict[str, list[float]] = defaultdict(list)

    for d in deals:
        status = _get_status(d)
        if status.lower() == "deal status":
            continue
        sector = _get_sector(d)
        val = _get_deal_value(d)
        if val is not None:
            sectors[sector].append(val)

    result = {}
    for sector, vals in sorted(sectors.items(), key=lambda x: -sum(x[1])):
        result[sector] = {
            "total_value": round(sum(vals), 2),
            "deal_count": len(vals),
            "avg_deal_size": round(sum(vals) / len(vals), 2) if vals else 0,
        }

    return result


def revenue_metrics(deals: list[dict]) -> dict:
    """
    Compute revenue / win-rate metrics from the Deals board.
    
    Won = 'Won' or 'Done' status
    Lost = 'Dead' status
    """
    won_values: list[float] = []
    lost_values: list[float] = []
    all_values: list[float] = []

    for d in deals:
        status = _get_status(d).lower()
        if status == "deal status":
            continue

        val = _get_deal_value(d)
        if val is None:
            continue

        all_values.append(val)
        if status in DEAL_WON_STATUSES:
            won_values.append(val)
        elif status in DEAL_LOST_STATUSES:
            lost_values.append(val)

    total_won = sum(won_values)
    total_lost = sum(lost_values)
    total_pipeline = sum(all_values)
    decided = len(won_values) + len(lost_values)

    return {
        "total_revenue_won": round(total_won, 2),
        "total_lost_value": round(total_lost, 2),
        "total_pipeline_value": round(total_pipeline, 2),
        "won_deal_count": len(won_values),
        "lost_deal_count": len(lost_values),
        "total_deal_count": len(all_values),
        "win_rate": round(len(won_values) / decided * 100, 1) if decided else 0,
        "avg_won_deal_size": round(total_won / len(won_values), 2) if won_values else 0,
    }


# ── Work Order Analytics ──

def work_order_metrics(work_orders: list[dict]) -> dict:
    """
    Compute work order metrics from the Work Orders board.
    
    Statuses: Completed, Not Started, In Progress, etc.
    """
    total_value = 0.0
    completed_value = 0.0
    status_counts: dict[str, int] = defaultdict(int)
    sector_values: dict[str, float] = defaultdict(float)
    count = 0

    for wo in work_orders:
        status = _get_status(wo)
        val = _get_deal_value(wo)

        status_counts[status] += 1

        if val is not None:
            total_value += val
            count += 1
            sector_values[_get_sector(wo)] += val

            if status.lower() in WO_COMPLETED_STATUSES:
                completed_value += val

    return {
        "total_work_order_value": round(total_value, 2),
        "completed_value": round(completed_value, 2),
        "pending_value": round(total_value - completed_value, 2),
        "work_order_count": count,
        "avg_work_order_size": round(total_value / count, 2) if count else 0,
        "status_breakdown": dict(status_counts),
        "sector_breakdown": {k: round(v, 2) for k, v in sorted(sector_values.items(), key=lambda x: -x[1])},
    }


def combined_overview(deals: list[dict], work_orders: list[dict]) -> dict:
    """
    Executive overview combining deals pipeline + work orders.
    """
    p = pipeline_metrics(deals)
    r = revenue_metrics(deals)
    wo = work_order_metrics(work_orders)

    return {
        "deals_pipeline": {
            "total_value": p["total_pipeline_value"],
            "active_value": p["active_pipeline_value"],
            "deal_count": p["deal_count"],
            "stage_breakdown": p["stage_breakdown"],
        },
        "revenue": {
            "won": r["total_revenue_won"],
            "lost": r["total_lost_value"],
            "win_rate_pct": r["win_rate"],
        },
        "work_orders": {
            "total_value": wo["total_work_order_value"],
            "completed_value": wo["completed_value"],
            "pending_value": wo["pending_value"],
            "count": wo["work_order_count"],
            "status_breakdown": wo["status_breakdown"],
        },
    }