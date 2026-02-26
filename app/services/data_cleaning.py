import re
from app.utils.logger import logger

# Columns whose values should be parsed as numbers
_NUMERIC_KEYWORDS = {"value", "amount", "price", "cost", "revenue", "budget", "size"}


def _parse_numeric(value: str | None) -> float | None:
    """Attempt to parse a string as a numeric value, stripping currency symbols."""
    if value is None:
        return None
    cleaned = re.sub(r"[^\d.\-]", "", str(value).strip())
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def _is_numeric_column(key: str) -> bool:
    """Heuristic: does the column name suggest numeric data?"""
    return any(kw in key for kw in _NUMERIC_KEYWORDS)


def normalize_items(items: list[dict]) -> tuple[list[dict], list[str]]:
    """
    Clean and normalize Monday.com board items.

    - Lowercases and snake_cases column titles
    - Converts numeric-looking columns to floats
    - Tracks data quality issues

    Returns:
        (normalized_rows, quality_issues)
    """
    normalized: list[dict] = []
    issues: list[str] = []

    for item in items:
        row: dict = {"name": item.get("name", "Unnamed")}

        for col in item.get("column_values", []):
            title = col.get("column", {}).get("title", "unknown")
            key = title.lower().strip().replace(" ", "_")
            value = col.get("text")

            # Track missing values
            if value in ("", None):
                issues.append(f"Missing value in '{key}' for '{row['name']}'")
                row[key] = None
                continue

            # Convert numeric columns
            if _is_numeric_column(key):
                numeric = _parse_numeric(value)
                if numeric is not None:
                    row[key] = numeric
                else:
                    issues.append(
                        f"Non-numeric value '{value}' in numeric column '{key}' for '{row['name']}'"
                    )
                    row[key] = value
            else:
                row[key] = value.strip()

        normalized.append(row)

    if issues:
        logger.warning(f"Data quality: {len(issues)} issues found during normalization")

    return normalized, issues