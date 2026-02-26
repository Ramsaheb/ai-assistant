# Decision Log — Monday.com Business Intelligence Agent

**Project:** Monday.com BI Agent &nbsp;|&nbsp; **Stack:** FastAPI · Python · Groq LLM &nbsp;|&nbsp; **Hosting:** Railway &nbsp;|&nbsp; **Date:** February 2026

---

## 1. Architecture & Framework Selection

The backend is built on **FastAPI** for its async-native request handling, automatic OpenAPI documentation, and Pydantic-first data validation — all critical for a high-performance BI service. Data is sourced exclusively through the **Monday.com GraphQL API v2**, which provides typed, structured access to board items with cursor-based pagination. This combination delivers sub-second response times for analytical queries while maintaining a minimal dependency footprint (no Pandas, no ORM). The frontend is a single `index.html` served directly by FastAPI, eliminating the need for a separate build pipeline or CORS configuration and enabling a one-command deployment on Railway via `uvicorn`.

## 2. Live Data Strategy — No-Cache Policy

A deliberate **no-cache architecture** was adopted: every inbound query triggers a live GraphQL call to Monday.com. There is no in-memory cache, no Redis layer, and no TTL-based invalidation. This guarantees that the end user — in this case, the founder — always sees **real-time board state** (deal values, statuses, work-order progress) at the moment of asking. The latency cost is modest (~1–2 s per round-trip) and acceptable for an executive dashboard where data freshness outweighs millisecond response times.

## 3. Data Resilience — Handling 600+ Quality Issues

Monday.com boards contained significant data inconsistency. The cleaning pipeline resolved **over 600 data-quality issues** across 351 Deals and 181 Work Orders, including:

- **Currency normalization:** Stripped `₹`, `$`, and comma separators from monetary fields so values parse cleanly to floats (e.g., `"₹1,50,000"` → `150000.0`).
- **Null / missing-value handling:** Items such as *Sakura* carried blank or malformed fields. The pipeline coerces these to safe defaults rather than allowing downstream `NoneType` crashes.
- **Header-row leakage & type coercion:** Auto-detects numeric columns via keyword heuristics (`amount`, `value`, `price`) and silently discards non-numeric artifacts that leak through the API response.

Every quality issue is tracked internally and surfaced in the API response, giving full transparency into what was cleaned and why.

## 4. Action Visibility — Transparent Agent Trace

The agent exposes a **visible execution trace** with every response. Each trace entry records which boards were queried (Deals, Work Orders, or both), the detected intent, the column mappings applied, and the data-quality issues encountered. This means the user can inspect exactly which API calls the agent made and how it arrived at its answer — a critical trust signal for executive-facing analytics.

## 5. Sector Mapping — Nature of Work → Sector

The source boards use a *Nature of Work* column that contains free-text project descriptors. To enable structured business-intelligence filtering (e.g., "show me revenue by sector"), the pipeline **maps Nature of Work values to a normalized Sector column**. This mapping allows aggregation, comparison, and trend analysis across sectors without requiring the board owner to restructure their Monday.com schema.

## 6. Key Tradeoffs

| Decision | Trade-off | Mitigation |
|---|---|---|
| No-cache live fetching | Higher per-query latency (~1–2 s) | Acceptable for executive use-case; ensures data freshness |
| Keyword-based intent detection | May misclassify unusual phrasing | Defaults to `pipeline`; returns clarifying questions for vague queries |
| No Pandas dependency | Limited to built-in aggregations | Pure-Python `statistics` module covers current metrics; easy to extend |
| CORS open (`*`) | Not production-hardened | Should be restricted to known origins before GA release |

---

## Appendix: Sample Live Query & Agent Trace

The following is a real interaction captured from the deployed agent, demonstrating live data fetching, data cleaning, and the transparent execution trace.

> **User:** What is the total pipeline value?

> **BI Agent:** Our total pipeline value stands at **₹23.06 Cr**, with an active pipeline value of **₹6.88 Cr**. The average deal size is approximately **₹1.40 Cr**, and the median deal size is **₹11.01 L**. Notably, the deal count is 165, with a significant number of deals (127) marked as 'Dead', indicating a potential red flag in our sales conversion process. To improve our win rate, I recommend conducting a thorough analysis of the 'Dead' deals to identify key factors contributing to the losses and adjusting our sales strategy accordingly.

**Agent Execution Trace:**

| Timestamp | Event |
|---|---|
| 10:09:14 PM | Query received |
| 10:09:14 PM | Intent detected: `pipeline` |
| 10:09:16 PM | Fetched **351 deals** from Monday.com |
| 10:09:16 PM | Deals normalized · 351 rows · **630 quality issues** |
| 10:09:16 PM | Analytics computed (pipeline metrics) |
| 10:09:17 PM | LLM summary generated |

> ⚠ **630 data quality issues detected** — all resolved automatically by the cleaning pipeline (currency symbols stripped, nulls coerced, non-numeric artifacts discarded).

This trace confirms the core design principles in action: every query hits the **live API** (no cache), the data-cleaning pipeline handles **600+ quality issues** transparently, and the full execution path is **visible to the user** for auditability.

---

*This document summarises the principal engineering decisions made during development. All source code, API routes, and cleaning logic are available in the project repository.*