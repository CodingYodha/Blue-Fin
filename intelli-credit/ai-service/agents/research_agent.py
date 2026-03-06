import uuid
import os
import asyncio
import logging
import time
import re
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, TypedDict
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from tavily import AsyncTavilyClient
from anthropic import AsyncAnthropic
from dotenv import load_dotenv
from langgraph.graph import StateGraph, END
import json
from model_config import CLAUDE_RESEARCH_AGENT_MODEL
import search_backends

load_dotenv()

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("research_agent")

app = FastAPI(title="Web Research Agent module")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory job storage
jobs: Dict[str, Dict[str, Any]] = {}

# Rate limiting
MAX_CONCURRENT_JOBS = 3
job_semaphore = asyncio.Semaphore(MAX_CONCURRENT_JOBS)

# Caching logic
CACHE_DURATION = timedelta(hours=1)
result_cache: Dict[str, Dict[str, Any]] = {}

# Stats tracking
stats = {
    "total_jobs_run": 0,
    "total_time_seconds": 0.0,
    "escalated_jobs": 0
}

# Pydantic models
class ResearchRequest(BaseModel):
    company_name: str
    promoter_names: List[str]
    industry: str
    cin: Optional[str] = None

class ResearchResponse(BaseModel):
    job_id: str
    status: str

class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    current_step: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    
class StatsResponse(BaseModel):
    total_jobs_run: int
    avg_time_seconds: float
    escalation_rate: float

# LangGraph state schema
class ResearchState(TypedDict):
    company_name: str
    promoter_names: List[str]
    industry: str
    cin: Optional[str]
    search_results: Dict[str, List[Any]] # Any because we'll convert SearchResult to dict
    escalation_triggered: bool
    triggered_keywords: List[str]
    escalation_results: List[Any]
    deep_search_backend: str
    escalation_query_count: int
    verified_findings: List[Dict[str, Any]]
    rejected_findings: List[Dict[str, Any]]
    entity_verification_ran: bool
    risk_signals: List[str]
    classification: Dict[str, Any] # Store the parsed JSON output from Claude

class VerifiedFinding(BaseModel):
    result: Dict[str, Any]
    match: Optional[bool]
    confidence: str
    reason: str

class SearchResult(BaseModel):
    title: str
    url: str
    content: str
    score: float

class TavilySearchTool:
    def __init__(self):
        self.api_key = os.getenv("TAVILY_API_KEY")
        if not self.api_key:
            logger.warning("TAVILY_API_KEY is not set. Search tool won't work.")
        self.client = AsyncTavilyClient(api_key=self.api_key) if self.api_key else None

    async def search(self, query: str, max_results: int = 5) -> List[SearchResult]:
        if not self.client:
            logger.error("No Tavily API key found.")
            return []
        
        try:
            response = await self.client.search(
                query=query, 
                search_depth="advanced", 
                max_results=max_results
            )
            results = response.get('results', [])
            
            parsed_results = []
            for r in results:
                parsed_results.append(
                    SearchResult(
                        title=r.get('title', ''),
                        url=r.get('url', ''),
                        content=r.get('content', ''),
                        score=r.get('score', 0.0)
                    )
                )
            return parsed_results
        except Exception as e:
            logger.error(f"Tavily search API error: {e}")
            return []

    async def search_with_retry(self, query: str, retries: int = 2, max_results: int = 5) -> List[SearchResult]:
        for attempt in range(retries + 1):
            try:
                results = await self.search(query, max_results)
                if results:
                    return results
            except Exception as e:
                logger.error(f"Attempt {attempt + 1} failed: {e}")
            
            if attempt < retries:
                await asyncio.sleep(1) # simple backoff
                
        return []

@app.get("/health")
async def health_check():
    return {"status": "ok"}

async def run_parallel_searches(
    tool: TavilySearchTool,
    company_name: str,
    promoter_names: List[str],
    industry: str
) -> Dict[str, List[SearchResult]]:
    start_time = time.time()
    
    # We'll just use the first promoter name for the searches to keep it simple,
    # or join them if there are multiple.
    primary_promoter = promoter_names[0] if promoter_names else "Unknown Promoter"
    
    # Input sanitization
    def sanitize(text: str) -> str:
        # Strip all non-alphanumeric/space characters to prevent injection
        return re.sub(r'[^a-zA-Z0-9\s]', '', text).strip()
        
    s_company = sanitize(company_name)
    s_promoter = sanitize(primary_promoter)
    
    queries = {
        "promoter_risk": f"{s_promoter} NCLT fraud litigation India",
        "credit_history": f"{s_company} credit rating downgrade RBI",
        "sector_outlook": f"{s_company} {industry} sector outlook 2024 2025",
        "mca_check": f"{s_promoter} MCA director disqualification",
        "default_history": f"{s_company} default NPA bank"
    }

    # Create a list of tasks for asyncio.gather
    # We use search_with_retry to ensure robustness
    tasks = [
        tool.search_with_retry(query, retries=2, max_results=3) 
        for query in queries.values()
    ]
    
    # Run all 5 searches concurrently
    results_list = await asyncio.gather(*tasks)
    
    end_time = time.time()
    logger.info(f"✅ Parallel search for {company_name} completed in {end_time - start_time:.2f} seconds")
    
    # Zip the keys back with their respective results
    return dict(zip(queries.keys(), results_list))

# --- LangGraph Nodes ---

async def run_base_searches(state: ResearchState) -> ResearchState:
    logger.info("Node: run_base_searches")
    tool = TavilySearchTool()
    results = await run_parallel_searches(
        tool, 
        state["company_name"], 
        state["promoter_names"], 
        state["industry"]
    )
    
    # Convert SearchResult objects to dicts for JSON serialization in state
    dict_results = {}
    for key, result_list in results.items():
        dict_results[key] = [r.model_dump() for r in result_list]
        
    return {"search_results": dict_results}

async def check_escalation(state: ResearchState) -> ResearchState:
    logger.info("Node: check_escalation")
    keywords = ["fraud", "NCLT", "NPA", "default", "arrested", "ED", "CBI", "Enforcement Directorate", "money laundering"]
    keywords_lower = [k.lower() for k in keywords]
    
    triggered_keywords = []
    
    # Scan all base search results for keywords
    for category, results_list in state["search_results"].items():
        for result in results_list:
            text_to_check = f"{result['title']} {result['content']}".lower()
            for keyword in keywords_lower:
                if keyword in text_to_check and keyword not in triggered_keywords:
                    logger.warning(f"Escalation triggered by keyword match in {category}: {result['title']}")
                    triggered_keywords.append(keyword)
                    
    return {
        "escalation_triggered": len(triggered_keywords) > 0,
        "triggered_keywords": triggered_keywords
    }

def should_escalate(state: ResearchState) -> str:
    if state.get("escalation_triggered", False):
        return "run_escalation_searches"
    return "verify_entity_match"

async def run_escalation_searches(state: ResearchState) -> ResearchState:
    logger.info("Node: run_escalation_searches")
    company_name = state["company_name"]
    promoter_names = state["promoter_names"]
    triggered_keywords = state.get("triggered_keywords", [])
    
    queries = search_backends.build_escalation_queries(company_name, promoter_names, triggered_keywords)
    
    all_results = []
    final_backend = ""
    query_count = len(queries)
    
    for query in queries:
        result = await search_backends.deep_search(query, num_results=5)
        final_backend = result.backend
        all_results.extend([r.model_dump() for r in result.results])
        if "duckduckgo" in final_backend:
            await asyncio.sleep(1)
            
    logger.info(f"Deep search complete: {query_count} queries via {final_backend}. Found {len(all_results)} results.")
        
    return {
        "escalation_results": all_results,
        "deep_search_backend": final_backend,
        "escalation_query_count": query_count
    }

async def verify_entity_match(state: ResearchState) -> ResearchState:
    logger.info("Node: verify_entity_match")
    company_name = state["company_name"]
    promoter_names = state["promoter_names"]
    cin = state.get("cin")

    all_results = []
    for category, results_list in state.get("search_results", {}).items():
        all_results.extend(results_list)
    all_results.extend(state.get("escalation_results", []))

    LEGAL_KEYWORDS = ["NCLT", "court", "petition", "FIR", "arrested", "ED",
                      "fraud", "default", "NPA", "SEBI", "CBI", "DRT", "SARFAESI"]

    legal_results = [
        r for r in all_results
        if any(kw.lower() in (r.get("title", "") + " " + r.get("snippet", r.get("content", ""))).lower() for kw in LEGAL_KEYWORDS)
    ]

    if not legal_results:
        return {
            "verified_findings": [], 
            "rejected_findings": [], 
            "entity_verification_ran": True
        }

    verified = []
    rejected = []
    client = AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    for result in legal_results:
        title = result.get("title", "")
        url = result.get("url", "")
        snippet = result.get("snippet", result.get("content", ""))
        
        verification_prompt = f"""You are an Entity Resolution AI for Indian corporate credit assessment.

A web search returned the following legal finding. Determine if it refers to the SAME
company/person as the loan applicant, or a different entity with a similar name.

LOAN APPLICANT:
- Company Name: {company_name}
- Promoter Names: {', '.join(promoter_names)}
- CIN: {cin or 'Not available'}

SEARCH RESULT:
Title: {title}
URL: {url}
Snippet: {snippet}

VERIFICATION TASK:
Does this search result refer to the SAME company or promoter as the loan applicant?

Rules:
- If the result mentions BOTH a matching promoter name AND the company name → MATCH: TRUE
- If the result mentions ONLY the name but a DIFFERENT company → MATCH: FALSE
- If the result mentions the CIN or DIN and it matches → MATCH: TRUE (strong signal)
- If uncertain (insufficient context) → MATCH: UNCERTAIN

Return ONLY this JSON, nothing else:
{{"match": true/false/null, "confidence": "HIGH"/"MEDIUM"/"LOW", "reason": "one sentence explanation"}}"""

        try:
            response = await client.messages.create(
                model=CLAUDE_RESEARCH_AGENT_MODEL,
                max_tokens=200,
                messages=[{"role": "user", "content": verification_prompt}]
            )
            raw_output = response.content[0].text
            
            try:
                if "```json" in raw_output:
                    json_str = raw_output.split("```json")[1].split("```")[0].strip()
                elif "```" in raw_output:
                    json_str = raw_output.split("```")[1].split("```")[0].strip()
                else:
                    json_str = raw_output.strip()
                parsed = json.loads(json_str)
            except json.JSONDecodeError:
                parsed = {}
            
            match = parsed.get("match")
            confidence = parsed.get("confidence", "LOW")
            reason = parsed.get("reason", "Verification parse error" if not parsed else "")

            finding_dict = {
                "result": result,
                "match": match,
                "confidence": confidence,
                "reason": reason
            }

            if match is True:
                verified.append(finding_dict)
            elif match is False:
                rejected.append(finding_dict)
            else: 
                finding_dict["confidence"] = "LOW"
                verified.append(finding_dict)
        except Exception as e:
            logger.error(f"Entity verification API error: {e}")
            verified.append({
                "result": result,
                "match": None,
                "confidence": "LOW",
                "reason": f"API error: {str(e)}"
            })

    logger.info(
        f"Entity verification: {len(verified)} verified, "
        f"{len(rejected)} rejected (name collision), "
        f"{len([v for v in verified if v.get('confidence') == 'LOW'])} uncertain"
    )
    
    return {
        "verified_findings": verified,
        "rejected_findings": rejected,
        "entity_verification_ran": True
    }

async def extract_risk_signals(state: ResearchState) -> ResearchState:
    logger.info("Node: extract_risk_signals")
    # A simple mock extraction for now.
    signals = []
    if state.get("escalation_triggered", False):
        signals.append("Automated escalation was triggered due to negative keywords found in base search.")
        if state.get("escalation_results"):
            signals.append(f"Found {len(state['escalation_results'])} deep records from escalating searches.")
            
    if state.get("rejected_findings"):
        signals.append(f"Entity verification rejected {len(state['rejected_findings'])} findings as name collisions.")
        
    if not signals:
        signals.append("No immediate red flags detected.")
        
    return {"risk_signals": signals}

async def classify_risks(state: ResearchState) -> ResearchState:
    logger.info("Node: classify_risks")
    client = AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    
    if not client.api_key:
        logger.warning("ANTHROPIC_API_KEY missing. Returning fallback classification.")
        return {"classification": {"error": "API key missing"}}
        
    # Combine all search text
    combined_text = ""
    for category, results in state.get("search_results", {}).items():
        combined_text += f"\n--- {category.upper()} ---\n"
        for r in results:
            combined_text += f"Title: {r['title']}\nContent: {r['content']}\n"
            
    if "escalation_results" in state:
        combined_text += f"\n--- ESCALATION RESULTS ---\n"
        for r in state["escalation_results"]:
             content = r.get('snippet', r.get('content', ''))
             combined_text += f"Title: {r['title']}\nContent: {content}\n"
                 
    # Truncate to avoid massive token usage during testing
    combined_text = combined_text[:3000]

    system_prompt = """You are a credit risk analyst. Given web search results about a company and its promoters, extract structured risk signals. Always respond in valid JSON only."""
    
    user_prompt = f"""Search results: {combined_text}
Company: {state['company_name']}
Promoters: {', '.join(state['promoter_names'])}

Respond ONLY with this JSON:
{{
  "promoter_risk": "LOW" | "MEDIUM" | "HIGH",
  "promoter_risk_reason": "one line explanation",
  "litigation_risk": "NONE" | "HISTORICAL" | "ACTIVE",
  "litigation_detail": "specific case details if found, else null",
  "sector_risk": "TAILWIND" | "NEUTRAL" | "HEADWIND",
  "sector_reason": "one line",
  "key_findings": ["finding 1", "finding 2"],
  "sources": ["url1", "url2"]
}}"""

    try:
        response = await client.messages.create(
            model=CLAUDE_RESEARCH_AGENT_MODEL,
            max_tokens=1000,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}]
        )
        
        # Raw text from Claude
        raw_output = response.content[0].text
        
        # safely parse JSON
        try:
            # Often LLMs wrap JSON in markdown markdown blocks
            if "```json" in raw_output:
                json_str = raw_output.split("```json")[1].split("```")[0].strip()
            elif "```" in raw_output:
                json_str = raw_output.split("```")[1].split("```")[0].strip()
            else:
                json_str = raw_output.strip()
                
            parsed_json = json.loads(json_str)
        except json.JSONDecodeError:
            logger.error(f"Failed to parse Claude JSON output: {raw_output}")
            parsed_json = {"error": "Failed to parse JSON", "raw_output": raw_output}
            
        return {"classification": parsed_json}
        
    except Exception as e:
        logger.error(f"Anthropic API error: {e}")
        return {"classification": {"error": str(e)}}

# --- Compile Graph ---
workflow = StateGraph(ResearchState)

# Wrap nodes to update job state during execution
def make_tracked_node(node_name: str, original_node):
    async def tracked_node(state: ResearchState) -> ResearchState:
        # We can pass the job_id in the state, but since these are stateless functions normally,
        # we'll use a hack to grab job_id if we inject it into the state or closure.
        # Alternatively, we just log it. For this scaffold, we'll update the global job store
        # if the job_id is present in the state (we'll add it to ResearchState temporarily).
        job_id = state.get("job_id")
        if job_id and job_id in jobs:
            jobs[job_id]["current_step"] = node_name
        
        return await original_node(state)
    return tracked_node

# Add job_id to typedef for tracking
class ResearchState(TypedDict):
    job_id: str
    company_name: str
    promoter_names: List[str]
    industry: str
    cin: Optional[str]
    search_results: Dict[str, List[Any]]
    escalation_triggered: bool
    triggered_keywords: List[str]
    escalation_results: List[Any]
    deep_search_backend: str
    escalation_query_count: int
    verified_findings: List[Dict[str, Any]]
    rejected_findings: List[Dict[str, Any]]
    entity_verification_ran: bool
    risk_signals: List[str]
    classification: Dict[str, Any]


workflow.add_node("run_base_searches", make_tracked_node("run_base_searches", run_base_searches))
workflow.add_node("check_escalation", make_tracked_node("check_escalation", check_escalation))
workflow.add_node("run_escalation_searches", make_tracked_node("run_escalation_searches", run_escalation_searches))
workflow.add_node("verify_entity_match", make_tracked_node("verify_entity_match", verify_entity_match))
workflow.add_node("extract_risk_signals", make_tracked_node("extract_risk_signals", extract_risk_signals))
workflow.add_node("classify_risks", make_tracked_node("classify_risks", classify_risks))

workflow.set_entry_point("run_base_searches")
workflow.add_edge("run_base_searches", "check_escalation")
workflow.add_conditional_edges("check_escalation", should_escalate)
workflow.add_edge("run_escalation_searches", "verify_entity_match")
workflow.add_edge("verify_entity_match", "extract_risk_signals")
workflow.add_edge("extract_risk_signals", "classify_risks")
workflow.add_edge("classify_risks", END)

research_graph = workflow.compile()

async def execute_research_graph(job_id: str, request: ResearchRequest):
    start_time = time.time()
    
    try:
        jobs[job_id]["status"] = "running"
        jobs[job_id]["current_step"] = "initializing"
        
        initial_state = {
            "job_id": job_id,
            "company_name": request.company_name,
            "promoter_names": request.promoter_names,
            "industry": request.industry,
            "search_results": {},
            "escalation_triggered": False,
            "triggered_keywords": [],
            "escalation_results": [],
            "deep_search_backend": "",
            "escalation_query_count": 0,
            "verified_findings": [],
            "rejected_findings": [],
            "entity_verification_ran": False,
            "cin": getattr(request, "cin", None),
            "risk_signals": [],
            "classification": {}
        }
        
        # Enforce 30 second strict timeout on the entire graph
        final_state = await asyncio.wait_for(
            research_graph.ainvoke(initial_state),
            timeout=30.0
        )
        
        jobs[job_id]["status"] = "completed"
        jobs[job_id]["current_step"] = "done"
        
        final_classification = final_state.get("classification", {})
        jobs[job_id]["result"] = final_classification
        jobs[job_id]["risk_signals"] = final_state.get("risk_signals", [])
        
        # Update cache
        cache_key = request.company_name.lower().strip()
        result_cache[cache_key] = {
            "timestamp": datetime.now(),
            "classification": final_classification,
            "risk_signals": final_state.get("risk_signals", [])
        }
        
        # Update Stats
        time_taken = time.time() - start_time
        escalated = final_state.get("escalation_triggered", False)
        
        stats["total_jobs_run"] += 1
        stats["total_time_seconds"] += time_taken
        if escalated:
            stats["escalated_jobs"] += 1
            
        # Structured Logging    
        logger.info(
            json.dumps({
                "event": "job_completed",
                "job_id": job_id,
                "company": request.company_name,
                "time_taken_sec": round(time_taken, 2),
                "escalation_triggered": escalated,
                "promoter_risk": final_classification.get("promoter_risk", "UNKNOWN")
            })
        )
        
    except asyncio.TimeoutError:
        logger.error(f"Job {job_id} failed: Timed out after 30 seconds")
        jobs[job_id]["status"] = "timeout"
        jobs[job_id]["current_step"] = "killed"
        jobs[job_id]["result"] = {"error": "Research task exceeded 30-second timeout limit"}
    except Exception as e:
        logger.error(f"Job {job_id} failed: {e}")
        jobs[job_id]["status"] = "failed"
        jobs[job_id]["current_step"] = "error"
        jobs[job_id]["result"] = {"error": str(e)}

@app.post("/research", response_model=ResearchResponse)
async def start_research(request: ResearchRequest, background_tasks: BackgroundTasks):
    
    # 1. Check Rate Limit (Semaphore)
    if job_semaphore.locked():
         raise HTTPException(status_code=429, detail="Too many concurrent research tasks. Please try again later.")
    
    # 2. Check Cache
    cache_key = request.company_name.lower().strip()
    if cache_key in result_cache:
        cached_data = result_cache[cache_key]
        if datetime.now() - cached_data["timestamp"] < CACHE_DURATION:
            job_id = f"cached_{str(uuid.uuid4())[:8]}"
            jobs[job_id] = {
                "status": "completed",
                "current_step": "done",
                "request_data": request.model_dump(),
                "result": cached_data["classification"],
                "risk_signals": cached_data["risk_signals"]
            }
            logger.info(json.dumps({"event": "cache_hit", "company": request.company_name}))
            return ResearchResponse(job_id=job_id, status="completed")
    
    # 3. Queue New Job
    job_id = str(uuid.uuid4())
    
    jobs[job_id] = {
        "status": "queued",
        "current_step": "queued",
        "request_data": request.model_dump(),
        "result": None,
        "risk_signals": []
    }
    
    # Background worker with semaphore acquisition
    async def run_with_semaphore():
        async with job_semaphore:
            await execute_research_graph(job_id, request)
            
    background_tasks.add_task(run_with_semaphore)
    
    return ResearchResponse(job_id=job_id, status="running")

@app.get("/research/stats", response_model=StatsResponse)
async def get_system_stats():
    total_jobs = stats["total_jobs_run"]
    avg_time = stats["total_time_seconds"] / total_jobs if total_jobs > 0 else 0.0
    esc_rate = (stats["escalated_jobs"] / total_jobs) * 100 if total_jobs > 0 else 0.0
    
    return StatsResponse(
        total_jobs_run=total_jobs,
        avg_time_seconds=round(avg_time, 2),
        escalation_rate=round(esc_rate, 2)
    )

@app.get("/research/{job_id}", response_model=JobStatusResponse)
async def get_research_status(job_id: str):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job_data = jobs[job_id]
    
    # To support frontend parity, merge risk_signals directly into the response payload
    # alongside the primary classification object
    final_payload = job_data.get("result", {})
    if isinstance(final_payload, dict) and "risk_signals" in job_data and job_data["risk_signals"]:
        final_payload["raw_risk_signals"] = job_data["risk_signals"]
        
    return JobStatusResponse(
        job_id=job_id,
        status=job_data["status"],
        current_step=job_data.get("current_step", ""),
        result=final_payload
    )

if __name__ == "__main__":
    async def test():
        print("\n--- Testing LangGraph Agent ---")
        
        company = "Reliance Industries"
        promoters = ["Mukesh Ambani"]
        industry = "Energy and Telecom"
        
        initial_state = {
            "job_id": "test_job_123",
            "company_name": company,
            "promoter_names": promoters,
            "industry": industry,
            "search_results": {},
            "escalation_triggered": False,
            "triggered_keywords": [],
            "escalation_results": [],
            "deep_search_backend": "",
            "escalation_query_count": 0,
            "verified_findings": [],
            "rejected_findings": [],
            "entity_verification_ran": False,
            "cin": None,
            "risk_signals": [],
            "classification": {}
        }
        
        # Mock global jobs dict for testing script
        jobs["test_job_123"] = {}
        
        final_state = await research_graph.ainvoke(initial_state)
        
        print(f"\nEscalation Triggered: {final_state['escalation_triggered']}")
        print("\nRisk Signals:")
        for signal in final_state['risk_signals']:
            print(f"- {signal}")
            
        print("\nClassification:")
        print(json.dumps(final_state.get('classification', {}), indent=2))
            
    asyncio.run(test())
