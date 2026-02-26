# Monday.com BI Agent — SkyLark Drones

An AI-powered Business Intelligence agent that connects to Monday.com boards (Deals + Work Orders) and delivers founder-level insights through a conversational chat interface with full chain-of-thought tracing.

## Live Demo

```bash
# Start the server
uvicorn app.main:app --reload

# Open browser
http://localhost:8000
```

The frontend is served directly from FastAPI at `/` — no separate setup needed.

## Features

### Core
- **Conversational chat interface** — multi-turn conversation with follow-up context
- **Live Monday.com integration** — every query triggers real-time GraphQL API calls (no caching)
- **Two-board querying** — Deals board + Work Orders board queried independently or combined
- **Smart intent detection** — routes to pipeline, sector, revenue, work order, or overview analytics
- **AI-generated executive summaries** — Groq LLM (Llama 3.3 70B) with SkyLark Drones context
- **Clarifying questions** — asks for specifics when query is too vague
- **Full transparency** — expandable agent trace on every response showing API calls, data normalization, analytics

### Data Resilience
- Handles missing/null values across all columns
- Normalizes inconsistent formats (currency symbols, number formats)
- Auto-detects numeric columns via keyword heuristics
- Reports data quality issues alongside every response
- Skips header rows that leak through the API

## Architecture

```
┌─────────────────┐     ┌──────────────────────────────────┐
│  Chat Frontend   │────▶│  FastAPI Backend (/api/query)    │
│  (served at /)   │◀────│                                   │
└─────────────────┘     │  ┌──────────────────────────────┐ │
                        │  │ 1. Clarification Check        │ │
                        │  │ 2. Follow-up Resolution       │ │
                        │  │ 3. Intent Detection           │ │
                        │  │ 4. Monday.com API (live)      │ │
                        │  │ 5. Data Cleaning              │ │
                        │  │ 6. Analytics Engine            │ │
                        │  │ 7. Groq LLM Summary           │ │
                        │  └──────────────────────────────┘ │
                        └──────────────────────────────────┘
                                      │
                    ┌─────────────────┼─────────────────┐
                    ▼                                   ▼
           Deals Board                        Work Orders Board
         (351 items)                            (181 items)
```

## Quick Start

### 1. Install dependencies

```bash
cd monday-bi-agent
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
```

| Variable | Required | Description |
|---|---|---|
| `MONDAY_API_TOKEN` | Yes | Monday.com API token |
| `DEALS_BOARD_ID` | Yes | Numeric board ID for Deals |
| `WORK_ORDERS_BOARD_ID` | Yes | Numeric board ID for Work Orders |
| `GROQ_API_KEY` | Yes | API key from [console.groq.com](https://console.groq.com) |

### 3. Run

```bash
uvicorn app.main:app --reload
```

Open `http://localhost:8000` for the chat UI, or `http://localhost:8000/docs` for Swagger API docs.

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/` | Chat UI |
| `GET` | `/api/health` | Health check |
| `POST` | `/api/query` | Submit a BI question |
| `GET` | `/docs` | Swagger API documentation |

### POST `/api/query`

**Request:**
```json
{
  "question": "How's the pipeline looking for mining sector?",
  "conversation_history": [
    {"role": "user", "content": "What is the total pipeline value?"},
    {"role": "assistant", "content": "The total pipeline stands at ₹2.3Cr..."}
  ]
}
```

**Response:**
```json
{
  "answer": "The Mining sector pipeline stands at ₹1.2Cr across 45 deals...",
  "trace": [
    {"timestamp": "2026-02-26T10:00:00Z", "message": "Query received"},
    {"timestamp": "2026-02-26T10:00:01Z", "message": "Intent detected: sector"},
    {"timestamp": "2026-02-26T10:00:02Z", "message": "Fetched 351 deals from Monday.com"},
    {"timestamp": "2026-02-26T10:00:02Z", "message": "Deals normalized | 351 rows | 163 quality issues"},
    {"timestamp": "2026-02-26T10:00:03Z", "message": "Analytics computed (sector metrics)"},
    {"timestamp": "2026-02-26T10:00:04Z", "message": "LLM summary generated"}
  ],
  "data_quality_issues": ["Missing value in 'person' for 'Deal X'"],
  "clarifying_question": null
}
```

## Analytics Intents

| Intent | Trigger Keywords | Boards Used |
|---|---|---|
| **pipeline** | pipeline, deal, funnel, opportunity | Deals |
| **sector** | sector, industry, mining, solar | Deals |
| **revenue** | revenue, won, win rate, conversion | Deals |
| **work_order** | work order, billing, invoice, collection | Work Orders |
| **overview** | overview, summary, dashboard, executive | Deals + Work Orders |

## Running Tests

```bash
pytest tests/ -v
```

31 tests covering: intent detection, numeric parsing, data normalization, pipeline/sector/revenue/work order analytics, combined overview, and API endpoints.

## Project Structure

```
monday-bi-agent/
├── app/
│   ├── main.py              # FastAPI app + frontend serving
│   ├── config.py            # Pydantic settings validation
│   ├── api/routes.py        # API endpoints
│   ├── models/schemas.py    # Request/response models (conversation history, clarifying questions)
│   └── services/
│       ├── agent.py         # Query orchestrator (clarify → intent → fetch → analyze → summarize)
│       ├── analytics.py     # Pipeline, sector, revenue, work order, overview metrics
│       ├── data_cleaning.py # Normalization & numeric parsing
│       └── monday_client.py # Monday.com GraphQL client with cursor-based pagination
├── frontend/
│   └── index.html           # Conversational chat UI
├── tests/
│   └── test_api.py          # 31 unit tests
├── decision_log/
│   └── decision_log.md      # Architecture & tradeoff decisions
├── requirements.txt
├── .env.example
└── README.md
```

## Example Questions

- "What is the total pipeline value?"
- "Show revenue breakdown by sector"
- "What is our deal win rate?"
- "Show work order billing status"
- "Give me an executive overview"
- "How's the energy sector pipeline?"
- "What about mining?" *(follow-up)*
