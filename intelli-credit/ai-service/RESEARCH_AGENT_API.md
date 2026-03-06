# Research Agent API — Quick Reference

**Base URL:** `http://ai-service:8001` (Docker) | `http://localhost:8001` (local dev)

---

## POST /api/v1/research-agent/run

Trigger the full LangGraph research pipeline for a loan application.

**Request:**
```json
{
  "job_id": "abc123",
  "company_name": "Mehta Textiles Pvt Ltd",
  "promoter_names": ["Rajesh Kumar Mehta", "Sunita Mehta"],
  "industry": "Textile Manufacturing",
  "cin": "U17111GJ2010PTC123456"
}
```

**Where to get these values:**
- `company_name`, `promoter_names`, `cin` → from `GET /api/v1/rag/extraction/{job_id}`
  (`entity_extraction.company_name`, `entity_extraction.promoters[].name`, `entity_extraction.cin`)
- `industry` → from `GET /api/v1/rag/extraction/{job_id}`
  (`qualitative_signals.management_commentary_summary` or hardcode from user upload form)

**Response (immediate):**
```json
{ "status": "processing", "job_id": "abc123", "message": "Research agent started" }
```

**Typical completion time:** 60–90 seconds.

---

## GET /api/v1/research-agent/status/{job_id}

Poll until `status = "ready"`. Returns the data the ML scorer needs.

**Key fields to pass to ML scoring (Section 7):**
- `promoter_risk` → Text Risk Signals Model input
- `litigation_risk` → Text Risk Signals Model input
- `sector_risk` → External Risk Model input
- `sector_sentiment_score` → External Risk Model input (range: -1.0 to +1.0)
- `key_findings` → CAM Generator input (Compliance Officer persona)

---

## Concurrency note for backend developer

Steps 5–8 (RAG) and Step 9 (Research Agent) can run **IN PARALLEL**.
They are both triggered after Step 3 (OCR) completes and are independent of each other.
This saves ~30–60 seconds of pipeline wall time.

**Recommended backend orchestration:**
- After `GET /api/v1/status/{job_id}` returns `"ready"` (Section 3 complete):
  - Fire `POST /api/v1/rag/ingest`    *(no await)*
  - Fire `POST /api/v1/research-agent/run`   *(no await)*
  - Poll both concurrently
  - Proceed to ML scoring only when BOTH are complete

---

## Search backend transparency (visible in SSE progress stream)

The agent logs which search backend it used for deep search:
- `"serper"` → Serper API used (credits available)
- `"duckduckgo_fallback"` → Serper credits exhausted, DuckDuckGo used automatically
- `"duckduckgo"` → `SERPER_API_KEY` not set, DuckDuckGo used directly

*No action required from backend — this is informational only.*

---

## Entity verification in practice

When a common Indian name like "Rajesh Kumar" appears in an NCLT case,
the `verify_entity_match` node checks if the case also mentions "Mehta Textiles".
If not → the result is rejected as a name collision and excluded from scoring.
Rejected results are logged in `research_agent_output.json` under `rejected_findings`.
The status response includes `entity_verification.rejected_findings` count.
The frontend can display: *"1 result excluded as name collision false positive"*

---

## Files written to shared volume

| File | Read by |
|------|---------|
| `/tmp/intelli-credit/{job_id}/research_agent_output.json` | full state (debugging) |
| `/tmp/intelli-credit/{job_id}/research_agent_summary.json` | ML scorer reads this |
