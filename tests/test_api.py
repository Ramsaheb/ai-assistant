"""Tests for the Monday.com BI Agent."""
import pytest
from unittest.mock import patch, MagicMock

from app.services.data_cleaning import normalize_items, _parse_numeric
from app.services.analytics import (
    pipeline_metrics, sector_metrics, revenue_metrics,
    work_order_metrics, combined_overview,
)
from app.services.agent import detect_intent, _needs_clarification, _resolve_follow_up


# ───────────────────────── detect_intent ─────────────────────────


class TestDetectIntent:
    def test_sector_keyword(self):
        assert detect_intent("Show breakdown by sector") == "sector"

    def test_industry_keyword(self):
        assert detect_intent("What industry has the most deals?") == "sector"

    def test_revenue_keyword(self):
        assert detect_intent("What is total revenue?") == "revenue"

    def test_win_rate_keyword(self):
        assert detect_intent("What is the win rate?") == "revenue"

    def test_pipeline_keyword(self):
        assert detect_intent("Show me the deal pipeline") == "pipeline"

    def test_work_order_keyword(self):
        assert detect_intent("Show work order status") == "work_order"

    def test_billing_keyword(self):
        assert detect_intent("What is the billing status?") == "work_order"

    def test_overview_keyword(self):
        assert detect_intent("Give me an executive overview") == "overview"

    def test_default_intent(self):
        assert detect_intent("Tell me something interesting") == "pipeline"


# ───────────────────────── _needs_clarification ─────────────────────────


class TestNeedsClarification:
    def test_vague_query(self):
        result = _needs_clarification("how are we doing")
        assert result is not None
        assert len(result["suggestions"]) > 0

    def test_short_query(self):
        result = _needs_clarification("hi")
        assert result is not None

    def test_specific_query_returns_none(self):
        result = _needs_clarification("What is the total pipeline value?")
        assert result is None


# ───────────────────────── _resolve_follow_up ─────────────────────────


class TestResolveFollowUp:
    def test_no_history(self):
        result = _resolve_follow_up("What about mining?", [])
        assert result == "What about mining?"

    def test_follow_up_with_signal(self):
        history = [{"role": "user", "content": "Show revenue by sector"}]
        result = _resolve_follow_up("What about mining?", history)
        assert "Follow-up to" in result
        assert "Show revenue by sector" in result

    def test_non_follow_up(self):
        history = [{"role": "user", "content": "Show revenue by sector"}]
        result = _resolve_follow_up("What is the pipeline?", history)
        assert result == "What is the pipeline?"


# ───────────────────────── _parse_numeric ─────────────────────────


class TestParseNumeric:
    def test_plain_number(self):
        assert _parse_numeric("1234.56") == 1234.56

    def test_currency_string(self):
        assert _parse_numeric("$5,000") == 5000.0

    def test_none_value(self):
        assert _parse_numeric(None) is None

    def test_empty_string(self):
        assert _parse_numeric("") is None

    def test_non_numeric(self):
        assert _parse_numeric("hello") is None


# ───────────────────────── normalize_items ─────────────────────────


class TestNormalizeItems:
    @staticmethod
    def _make_item(name, columns):
        return {
            "name": name,
            "column_values": [
                {"column": {"title": k}, "text": v} for k, v in columns.items()
            ],
        }

    def test_basic_normalization(self):
        item = self._make_item("Deal A", {"Sector": "Energy", "Value": "5000"})
        rows, issues = normalize_items([item])
        assert len(rows) == 1
        assert rows[0]["name"] == "Deal A"
        assert rows[0]["sector"] == "Energy"
        assert rows[0]["value"] == 5000.0
        assert issues == []

    def test_missing_value_tracked(self):
        item = self._make_item("Deal B", {"Sector": "", "Value": "1000"})
        rows, issues = normalize_items([item])
        assert rows[0]["sector"] is None
        assert len(issues) == 1
        assert "Missing value" in issues[0]

    def test_non_numeric_in_value_column(self):
        item = self._make_item("Deal C", {"Value": "TBD"})
        rows, issues = normalize_items([item])
        assert rows[0]["value"] == "TBD"
        assert len(issues) == 1
        assert "Non-numeric" in issues[0]


# ───────────────────────── pipeline_metrics ─────────────────────────


class TestPipelineMetrics:
    def test_basic_with_monday_statuses(self):
        """Test with actual Monday.com status labels."""
        deals = [
            {"name": "A", "amount": 489360, "status": "Open", "sector": "Mining"},
            {"name": "B", "amount": 611700, "status": "Working on it", "sector": "Powerline"},
            {"name": "C", "amount": 2348928, "status": "Dead", "sector": "Mining"},
        ]
        m = pipeline_metrics(deals)
        assert m["total_pipeline_value"] == 489360 + 611700 + 2348928
        assert m["deal_count"] == 3
        assert m["active_pipeline_value"] == 489360 + 611700  # Open + Working on it
        assert m["stage_breakdown"]["Open"] == 1
        assert m["stage_breakdown"]["Dead"] == 1

    def test_skips_header_row(self):
        """Header rows with status 'Deal Status' should be skipped."""
        deals = [
            {"name": "Header", "amount": 0, "status": "Deal Status"},
            {"name": "A", "amount": 1000, "status": "Open"},
        ]
        m = pipeline_metrics(deals)
        assert m["deal_count"] == 1
        assert "Deal Status" not in m["stage_breakdown"]

    def test_empty_deals(self):
        m = pipeline_metrics([])
        assert m["deal_count"] == 0
        assert m["total_pipeline_value"] == 0


# ───────────────────────── sector_metrics ─────────────────────────


class TestSectorMetrics:
    def test_basic(self):
        deals = [
            {"name": "A", "sector": "Mining", "amount": 489360, "status": "Open"},
            {"name": "B", "sector": "Mining", "amount": 611700, "status": "Open"},
            {"name": "C", "sector": "Powerline", "amount": 2348928, "status": "Open"},
        ]
        m = sector_metrics(deals)
        assert m["Mining"]["total_value"] == 489360 + 611700
        assert m["Mining"]["deal_count"] == 2
        assert m["Powerline"]["deal_count"] == 1

    def test_unknown_sector(self):
        deals = [{"name": "A", "amount": 100, "status": "Open"}]
        m = sector_metrics(deals)
        assert "Unknown" in m


# ───────────────────────── revenue_metrics ─────────────────────────


class TestRevenueMetrics:
    def test_with_actual_statuses(self):
        """Test with actual Monday.com statuses: Won, Done = won; Dead = lost."""
        deals = [
            {"name": "A", "amount": 489360, "status": "Won"},
            {"name": "B", "amount": 611700, "status": "Open"},
            {"name": "C", "amount": 2348928, "status": "Dead"},
            {"name": "D", "amount": 100000, "status": "Done"},
        ]
        m = revenue_metrics(deals)
        assert m["total_revenue_won"] == 489360 + 100000
        assert m["total_lost_value"] == 2348928
        assert m["won_deal_count"] == 2
        assert m["lost_deal_count"] == 1
        # win_rate = won / (won+lost) = 2/3 = 66.7%
        assert m["win_rate"] == pytest.approx(66.7, abs=0.1)

    def test_no_won_deals(self):
        deals = [
            {"name": "A", "amount": 1000, "status": "Open"},
        ]
        m = revenue_metrics(deals)
        assert m["total_revenue_won"] == 0
        assert m["won_deal_count"] == 0
        assert m["win_rate"] == 0


# ───────────────────────── work_order_metrics ─────────────────────────


class TestWorkOrderMetrics:
    def test_basic(self):
        wos = [
            {"name": "WO-1", "amount": 264398.08, "status": "Completed", "sector": "Mining"},
            {"name": "WO-2", "amount": 154150, "status": "Not Started", "sector": "Powerline"},
            {"name": "WO-3", "amount": 184980, "status": "Completed", "sector": "Mining"},
        ]
        m = work_order_metrics(wos)
        assert m["total_work_order_value"] == pytest.approx(264398.08 + 154150 + 184980, abs=0.01)
        assert m["completed_value"] == pytest.approx(264398.08 + 184980, abs=0.01)
        assert m["pending_value"] == pytest.approx(154150, abs=0.01)
        assert m["work_order_count"] == 3
        assert m["status_breakdown"]["Completed"] == 2
        assert m["status_breakdown"]["Not Started"] == 1

    def test_empty(self):
        m = work_order_metrics([])
        assert m["work_order_count"] == 0
        assert m["total_work_order_value"] == 0


# ───────────────────────── combined_overview ─────────────────────────


class TestCombinedOverview:
    def test_structure(self):
        deals = [{"name": "A", "amount": 1000, "status": "Open", "sector": "Mining"}]
        wos = [{"name": "WO-1", "amount": 500, "status": "Completed", "sector": "Mining"}]
        m = combined_overview(deals, wos)
        assert "deals_pipeline" in m
        assert "revenue" in m
        assert "work_orders" in m
        assert m["deals_pipeline"]["deal_count"] == 1
        assert m["work_orders"]["count"] == 1


# ───────────────────────── FastAPI endpoint ─────────────────────────


class TestAPI:
    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient
        from app.main import app
        return TestClient(app)

    def test_root_serves_html(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]

    def test_health(self, client):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "healthy"

    def test_query_validation_rejects_empty(self, client):
        resp = client.post("/api/query", json={"question": ""})
        assert resp.status_code == 422

    def test_query_with_conversation_history(self, client):
        """Verify that conversation_history is accepted in the request body."""
        resp = client.post("/api/query", json={
            "question": "hey there",
            "conversation_history": [
                {"role": "user", "content": "What is the pipeline?"},
                {"role": "assistant", "content": "The pipeline is..."},
            ],
        })
        # Short query with history should NOT trigger clarification (history present)
        assert resp.status_code == 200

    @patch("app.services.agent.fetch_board_items")
    @patch("app.services.agent.client")
    def test_query_success(self, mock_groq, mock_fetch, client):
        mock_fetch.return_value = [
            {
                "id": "1",
                "name": "Naruto",
                "column_values": [
                    {"column": {"title": "Person"}, "text": ""},
                    {"column": {"title": "Status"}, "text": "Open"},
                    {"column": {"title": "Date"}, "text": "2026-02-26"},
                    {"column": {"title": "Amount"}, "text": "489360"},
                    {"column": {"title": "Sector"}, "text": "Mining"},
                ],
            }
        ]
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="Great insight!"))]
        mock_groq.chat.completions.create.return_value = mock_response

        resp = client.post("/api/query", json={"question": "What is the pipeline?"})
        assert resp.status_code == 200
        data = resp.json()
        assert "answer" in data
        assert "trace" in data
        assert "clarifying_question" in data
        assert len(data["trace"]) > 0

    def test_clarifying_question_for_vague_query(self, client):
        """Vague queries without conversation history should get a clarifying question."""
        resp = client.post("/api/query", json={"question": "hi there"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["clarifying_question"] is not None
        assert len(data["clarifying_question"]["suggestions"]) > 0