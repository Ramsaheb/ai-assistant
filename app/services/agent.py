"""Query processing orchestrator — intent detection, analytics routing, LLM summary."""

from groq import Groq

from app.services.monday_client import fetch_board_items, MondayClientError
from app.services.data_cleaning import normalize_items
from app.services.analytics import (
    pipeline_metrics,
    sector_metrics,
    revenue_metrics,
    work_order_metrics,
    combined_overview,
)
from app.utils.logger import ToolTrace, logger
from app.config import settings

client = Groq(api_key=settings.GROQ_API_KEY)

# ── Intent keywords (order matters — first match wins) ──

_INTENT_MAP = {
    "work_order": [
        "work order", "wo ", "billing", "invoice", "collection",
        "execution", "delivery", "billed", "completed order",
        "pending order", "work_order",
    ],
    "overview": [
        "overview", "summary", "dashboard", "overall", "big picture",
        "executive", "everything", "full report",
    ],
    "sector": [
        "sector", "industry", "vertical", "segment", "mining",
        "powerline", "solar", "oil", "telecom",
    ],
    "revenue": [
        "revenue", "sales", "income", "won", "closed", "win rate",
        "conversion", "lost", "dead", "win", "loss",
    ],
    "pipeline": [
        "pipeline", "deal", "funnel", "opportunity", "prospect",
        "lead", "open deal", "active deal", "on hold",
    ],
}

# Queries that are too vague and need clarification
_VAGUE_PATTERNS = [
    "how are we doing",
    "what's happening",
    "tell me something",
    "any updates",
    "how's it going",
    "what's new",
]


def detect_intent(question: str) -> str:
    """Classify user question into an analytics intent using keyword matching."""
    q = question.lower()
    for intent, keywords in _INTENT_MAP.items():
        if any(kw in q for kw in keywords):
            return intent
    return "pipeline"  # default


def _needs_clarification(question: str) -> dict | None:
    """Check if the query is too vague and return a clarifying question if so."""
    q = question.lower().strip()
    if len(q) < 10 or any(vague in q for vague in _VAGUE_PATTERNS):
        return {
            "question": "Could you be more specific? I can help with several areas:",
            "suggestions": [
                "What is the total pipeline value?",
                "Show revenue breakdown by sector",
                "What is our deal win rate?",
                "Show work order billing status",
                "Give me an executive overview of everything",
            ],
        }
    return None


def _resolve_follow_up(question: str, history: list[dict]) -> str:
    """Resolve follow-up questions using conversation history."""
    if not history:
        return question

    q = question.lower().strip()
    follow_up_signals = [
        "what about", "and for", "how about", "same for",
        "now show", "also", "break it down", "more detail",
        "drill down", "compared to", "what else",
    ]

    if any(sig in q for sig in follow_up_signals):
        last_msgs = [m for m in history if m["role"] == "user"]
        if last_msgs:
            prev_q = last_msgs[-1]["content"]
            return f"(Follow-up to: '{prev_q}') {question}"

    return question


def generate_summary(
    question: str,
    metrics: dict,
    intent: str,
    conversation_history: list[dict] | None = None,
) -> str:
    """Ask Groq LLM to produce an executive summary from computed metrics."""
    system_prompt = """You are a business intelligence assistant for SkyLark Drones — a drone services company
operating in sectors like Mining, Powerline, Solar, Oil & Gas, and Telecom.

Context:
- Deal statuses: Open (active), Working on it (in progress), Won/Done (closed-won), Dead (lost), On Hold
- Work order statuses: Completed, Not Started, In Progress
- Currency is INR (Indian Rupees). Use ₹ symbol with lakhs/crores formatting.

Instructions:
- Write a concise executive-level insight (3-5 sentences).
- Highlight key numbers using ₹ symbol (e.g., ₹48.9L for lakhs, ₹2.3Cr for crores).
- Call out red flags (high dead rate, low win rate, pending collections).
- End with one specific, actionable recommendation.
- Use professional tone suitable for a founder/CEO.
- If this is a follow-up question, use context from conversation history."""

    messages = [{"role": "system", "content": system_prompt}]

    # Add conversation history for follow-up context
    if conversation_history:
        for msg in conversation_history[-6:]:  # last 3 turns
            messages.append({"role": msg["role"], "content": msg["content"]})

    user_content = f"""User Question: {question}
Analysis Type: {intent}
Computed Metrics:
{_format_metrics(metrics)}"""

    messages.append({"role": "user", "content": user_content})

    try:
        response = client.chat.completions.create(
            model=settings.LLM_MODEL,
            messages=messages,
            temperature=settings.LLM_TEMPERATURE,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"LLM generation failed: {e}")
        return f"Unable to generate summary. Raw metrics: {metrics}"


def _format_metrics(metrics: dict, indent: int = 0) -> str:
    """Pretty-format nested metrics dict for the LLM prompt."""
    lines = []
    prefix = "  " * indent
    for key, val in metrics.items():
        if isinstance(val, dict):
            lines.append(f"{prefix}{key}:")
            lines.append(_format_metrics(val, indent + 1))
        else:
            lines.append(f"{prefix}{key}: {val}")
    return "\n".join(lines)


def _fetch_and_normalize(board_id: str, trace: ToolTrace, label: str):
    """Fetch items from a board and normalize them. Returns (items, issues)."""
    raw = fetch_board_items(board_id)
    trace.add(f"Fetched {len(raw)} {label} from Monday.com")
    items, issues = normalize_items(raw)
    trace.add(f"{label.capitalize()} normalized | {len(items)} rows | {len(issues)} quality issues")
    return items, issues


async def process_query(
    question: str,
    conversation_history: list[dict] | None = None,
) -> dict:
    """End-to-end query pipeline: clarify → fetch → clean → analyze → summarize."""
    trace = ToolTrace()
    trace.add("Query received")

    history = conversation_history or []

    # Check if query needs clarification
    clarification = _needs_clarification(question)
    if clarification and not history:
        trace.add("Query is ambiguous — asking clarifying question")
        return {
            "answer": "I'd be happy to help! Your question is a bit broad — could you tell me what specifically you'd like to know?",
            "trace": trace.get(),
            "data_quality_issues": [],
            "clarifying_question": clarification,
        }

    try:
        # Resolve follow-ups using history
        resolved_question = _resolve_follow_up(question, history)
        if resolved_question != question:
            trace.add("Follow-up resolved with context from conversation history")

        intent = detect_intent(resolved_question)
        trace.add(f"Intent detected: {intent}")

        all_issues: list[str] = []

        # Always fetch deals
        deals, deal_issues = _fetch_and_normalize(
            settings.DEALS_BOARD_ID, trace, "deals"
        )
        all_issues.extend(deal_issues)

        # Fetch work orders if needed
        work_orders = []
        if intent in ("work_order", "overview") and settings.WORK_ORDERS_BOARD_ID:
            wo_items, wo_issues = _fetch_and_normalize(
                settings.WORK_ORDERS_BOARD_ID, trace, "work orders"
            )
            work_orders = wo_items
            all_issues.extend(wo_issues)

        # Route to correct analytics function
        if intent == "sector":
            metrics = sector_metrics(deals)
        elif intent == "revenue":
            metrics = revenue_metrics(deals)
        elif intent == "work_order":
            if work_orders:
                metrics = work_order_metrics(work_orders)
            else:
                metrics = {"error": "Work orders board not configured or empty"}
        elif intent == "overview":
            metrics = combined_overview(deals, work_orders)
        else:
            metrics = pipeline_metrics(deals)

        trace.add(f"Analytics computed ({intent} metrics)")

        # Generate LLM summary with conversation context
        answer = generate_summary(question, metrics, intent, history)
        trace.add("LLM summary generated")

        return {
            "answer": answer,
            "trace": trace.get(),
            "data_quality_issues": all_issues,
            "clarifying_question": None,
        }

    except MondayClientError as e:
        trace.add(f"Monday.com API error: {str(e)}")
        logger.error(f"MondayClientError: {e}")
        return {
            "answer": f"Failed to fetch data from Monday.com: {e}",
            "trace": trace.get(),
            "data_quality_issues": [],
            "clarifying_question": None,
        }

    except Exception as e:
        trace.add(f"Unexpected error: {str(e)}")
        logger.exception("Unhandled exception in process_query")
        return {
            "answer": "An unexpected error occurred while processing your query. Please try again.",
            "trace": trace.get(),
            "data_quality_issues": [],
            "clarifying_question": None,
        }