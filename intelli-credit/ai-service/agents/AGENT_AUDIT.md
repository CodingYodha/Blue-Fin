# Research Agent — Current State Audit

> **Generated from:** `ai-service/agents/research_agent.py` (583 lines)
> **Read-only audit — no code was modified.**

---

## ResearchState Fields

The `ResearchState(TypedDict)` is defined **twice** — once at line 79 (without `job_id`), then
redefined at line 375 (with `job_id` added for tracking). The **active** definition is:

```python
class ResearchState(TypedDict):
    job_id: str                              # injected for job tracking via make_tracked_node
    company_name: str                        # from ResearchRequest
    promoter_names: List[str]                # from ResearchRequest
    industry: str                            # from ResearchRequest
    search_results: Dict[str, List[Any]]     # base Tavily results (5 categories)
    escalation_triggered: bool               # set by check_escalation
    escalation_results: Dict[str, List[Any]] # deep search results (2 categories)
    risk_signals: List[str]                  # extracted risk signal strings
    classification: Dict[str, Any]           # Claude's structured JSON output
```

---

## Entry Point

```python
async def execute_research_graph(job_id: str, request: ResearchRequest)
```

- Called as a background task from `POST /research`
- Builds `initial_state` dict, runs `research_graph.ainvoke(initial_state)` with 30s timeout
- Stores result in `jobs[job_id]` and `result_cache[company_name]`
- Updates stats (total_jobs_run, total_time_seconds, escalated_jobs)

---

## Node: run_base_searches

**What it does:** Creates `TavilySearchTool()`, calls `run_parallel_searches()` which runs
5 concurrent Tavily queries with `search_depth="advanced"`, `max_results=3`, `retries=2`.

**Query construction** (uses sanitized `company_name` and first `promoter_names[0]`):

| Key | Query Template |
|-----|----------------|
| `promoter_risk` | `"{promoter} NCLT fraud litigation India"` |
| `credit_history` | `"{company} credit rating downgrade RBI"` |
| `sector_outlook` | `"{company} {industry} sector outlook 2024 2025"` |
| `mca_check` | `"{promoter} MCA director disqualification"` |
| `default_history` | `"{company} default NPA bank"` |

**Writes to state:** `search_results` — dict of 5 keys → list of `SearchResult.model_dump()` dicts.

---

## Node: check_escalation

**What it does:** Scans ALL base `search_results` (title + content) for escalation keywords.

**Keyword list (case-insensitive):**
```
fraud, NCLT, NPA, default, arrested, ED, CBI, Enforcement Directorate, money laundering
```

**Writes to state:** `escalation_triggered: bool` — `True` if any keyword found in any result.

---

## Node: run_escalation_searches (⚠️ WILL BE REPLACED)

**What it currently does:** Uses **Tavily** (same `TavilySearchTool`) for 2 deep queries:

| Key | Query Template |
|-----|----------------|
| `nclt_cases` | `"{promoter} NCLT case number status site:nclt.gov.in OR site:ecourts.gov.in"` |
| `ed_attachments` | `"{company} enforcement directorate ED attachment"` |

**Writes to state:** `escalation_results` — dict of 2 keys → list of result dicts.

**What will change:** Replace Tavily with Serper API (2500 free credits), with DuckDuckGo
fallback when Serper returns HTTP 429 or quota error.

---

## Node: extract_risk_signals

**What it does:** Simple keyword-based extraction (**not** a Claude call). Mock implementation:
- If `escalation_triggered`: adds "Automated escalation was triggered..." signal
- For each category in `escalation_results` with results: adds "Found deep records in {cat}."
- If nothing: adds "No immediate red flags detected."

**Writes to state:** `risk_signals: List[str]`

---

## Node: classify_risks

**What it does:** Claude API call for structured risk classification.

**Model:** `CLAUDE_RESEARCH_AGENT_MODEL` (from `model_config.py` → `claude-haiku-4-5-20251001`)

**Input:** Combines all `search_results` + `escalation_results` text (truncated to 3000 chars).

**System prompt:** "You are a credit risk analyst..." (respond in valid JSON only)

**Output JSON structure Claude is prompted to produce:**
```json
{
  "promoter_risk": "LOW | MEDIUM | HIGH",
  "promoter_risk_reason": "one line explanation",
  "litigation_risk": "NONE | HISTORICAL | ACTIVE",
  "litigation_detail": "specific case details if found, else null",
  "sector_risk": "TAILWIND | NEUTRAL | HEADWIND",
  "sector_reason": "one line",
  "key_findings": ["finding 1", "finding 2"],
  "sources": ["url1", "url2"]
}
```

**Writes to state:** `classification: Dict[str, Any]` — the parsed JSON above.

---

## Graph Wiring (Current)

```
Entry → run_base_searches
      → check_escalation
      → (conditional: should_escalate)
          ├── True  → run_escalation_searches → extract_risk_signals
          └── False → extract_risk_signals
      → classify_risks
      → END
```

**Edges:**
```python
workflow.set_entry_point("run_base_searches")
workflow.add_edge("run_base_searches", "check_escalation")
workflow.add_conditional_edges("check_escalation", should_escalate)
workflow.add_edge("run_escalation_searches", "extract_risk_signals")
workflow.add_edge("extract_risk_signals", "classify_risks")
workflow.add_edge("classify_risks", END)
```

**`should_escalate` function:** Returns `"run_escalation_searches"` if `escalation_triggered`,
else `"extract_risk_signals"`.

---

## FastAPI Endpoints (Current)

| Method | Path | Handler |
|--------|------|---------|
| `GET` | `/health` | `health_check()` |
| `POST` | `/research` | `start_research()` — queues background task with semaphore |
| `GET` | `/research/{job_id}` | `get_research_status()` — returns job status + result |
| `GET` | `/research/stats` | `get_system_stats()` — returns aggregate stats |

**Production hardening already present:**
- Rate limiting: `MAX_CONCURRENT_JOBS = 3` via `asyncio.Semaphore`
- Caching: `CACHE_DURATION = 1 hour`, keyed on `company_name.lower().strip()`
- Timeout: 30-second `asyncio.wait_for` on entire graph execution
- Input sanitization: `re.sub(r'[^a-zA-Z0-9\s]', '', text)` on all search inputs
- Structured logging with JSON events

---

## What Needs to Be Added

### 1. Serper API in `run_escalation_searches` (replace Tavily)
- Use Serper API (2500 free credits) for escalation deep searches
- Catch HTTP 429 / quota errors → fall back to DuckDuckGo automatically
- Log which search backend was used (Serper vs DuckDuckGo)

### 2. `verify_entity_match` node (V1 fix)
- New node: Claude-based entity disambiguation
- Runs after every legal finding to prevent wrongful rejections from common Indian name collisions
- Must be inserted after `run_escalation_searches`, before `extract_risk_signals`

### 3. `score_sector_sentiment` node (V3 fix)
- New node: Claude-based sentiment scoring
- Uses hardcoded Indian regulatory severity mappings
- FinBERT was never added — this is entirely new
- Must be inserted in the graph between appropriate nodes

### 4. Graph wiring update + output file
- Update `StateGraph` edges to include both new nodes
- Write output JSON to `/tmp/intelli-credit/{job_id}/research_output.json` for web developer integration
- Ensure FastAPI endpoint serves this file

---

## Dependencies

| Package | Purpose | Status |
|---------|---------|--------|
| `tavily` | Base web searches (5 queries) | ✅ Installed, used |
| `anthropic` | Claude risk classification | ✅ Installed, used |
| `langgraph` | StateGraph orchestration | ✅ Installed, used |
| `model_config` | Centralized model names | ✅ Imported |
| `serper` / `httpx` | Serper API for escalation | ❌ Not yet integrated |
| `duckduckgo_search` | DuckDuckGo fallback | ❌ Not yet installed |
