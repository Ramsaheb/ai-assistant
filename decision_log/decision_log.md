# Decision Log — Monday.com BI Agent

## Tech Stack Choices

| Component | Choice | Justification |
|---|---|---|
| **Backend** | FastAPI (Python) | Async-native, auto-generates OpenAPI/Swagger docs, Pydantic-first validation, fast development |
| **LLM** | Groq (Llama 3.3 70B) | Fastest inference available (~200ms), free tier sufficient, produces high-quality executive summaries |
| **Monday.com API** | GraphQL (direct) | Official API, cursor-based pagination for large boards, real-time data with no caching |
| **Frontend** | Single HTML file | Zero build step, served directly from FastAPI, easy to deploy as a single unit |
| **Validation** | Pydantic v2 + pydantic-settings | Type-safe request/response models, env var validation with helpful error messages on misconfiguration |
| **Testing** | pytest | Industry standard, clean fixtures, good for both unit and integration tests |

## Key Architecture Decisions

### 1. Two-Board Architecture
Both Deals (351 items) and Work Orders (181 items) are connected. The agent detects which board(s) to query based on intent — `sector`/`revenue`/`pipeline` → Deals only; `work_order` → Work Orders only; `overview` → both boards combined. This avoids unnecessary API calls while supporting cross-board queries.

### 2. Keyword-Based Intent Detection (Not LLM)
Chose deterministic keyword matching over LLM-based classification for intent routing. This is:
- **Faster** — no extra LLM call (~0ms vs ~200ms)
- **Transparent** — intent appears in trace, easy to debug
- **Reliable** — no hallucinated intents
- **Extensible** — adding new intents = adding keywords to a dict

The LLM is reserved for what it's best at: generating natural-language executive summaries from structured metrics.

### 3. Conversation History & Clarifying Questions
The API accepts `conversation_history` for follow-up context. Previous messages are passed to the LLM for coherent multi-turn conversations. When a query is too vague (<10 chars or matches vague patterns), the agent returns `clarifying_question` with suggested queries instead of guessing.

### 4. Data Cleaning Pipeline
Monday.com data is messy (missing values, inconsistent formats, header rows leaking through). The pipeline:
1. Lowercases & snake_cases column names for uniform access
2. Auto-detects numeric columns via keyword heuristics (`amount`, `value`, `price`)
3. Strips currency symbols (`$`, `₹`, commas) during parsing
4. Tracks every quality issue and returns them with the response

### 5. Frontend Served from FastAPI
The chat UI is a single `index.html` served by FastAPI at `/`. This means the prototype is a single `uvicorn` command — no separate frontend server, no CORS issues in production, easy to host on any Python platform (Render, Railway, etc.).

### 6. No Pandas, No Caching
- **No Pandas**: Pure Python dicts + `statistics.median()` is sufficient for current aggregations. Removes a heavy dependency and simplifies the install.
- **No caching**: Every query hits Monday.com live, as required. This ensures the founder always sees current data.

## Tradeoffs & Limitations

| Tradeoff | Impact | Mitigation |
|---|---|---|
| Keyword intent detection | May misclassify unusual phrasing | Default to `pipeline`; clarifying questions for vague queries |
| CORS open (`*`) | Not production-secure | Should be restricted for deployment |
| No auth on API | Anyone with the URL can query | Add API key middleware for production |
| Synchronous Monday.com requests | Blocks during GraphQL calls | Acceptable latency (~1-2s); could switch to `httpx.AsyncClient` if needed |
| Conversation history in request body | Client must maintain state | Simpler than server-side sessions; frontend handles it in JS |

## Monday.com Board Configuration

| Board | Items | Columns | Key Statuses |
|---|---|---|---|
| Deals | 351 | Person, Status, Date, Amount, Sector | Open, Working on it, Won, Done, Dead, On Hold |
| Work Orders | 181 | Person, Status, Date, Amount, Sector | Completed, Not Started, In Progress |