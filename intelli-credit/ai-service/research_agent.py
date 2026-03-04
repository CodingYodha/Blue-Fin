import uuid
import os
import asyncio
import logging
import time
from typing import List, Dict, Any, Optional, TypedDict
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from tavily import AsyncTavilyClient
from dotenv import load_dotenv
from langgraph.graph import StateGraph, END

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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

# Pydantic models
class ResearchRequest(BaseModel):
    company_name: str
    promoter_names: List[str]
    industry: str

class ResearchResponse(BaseModel):
    job_id: str
    status: str

class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    result: Optional[Dict[str, Any]] = None

# LangGraph state schema
class ResearchState(TypedDict):
    company_name: str
    promoter_names: List[str]
    industry: str
    search_results: Dict[str, List[Any]] # Any because we'll convert SearchResult to dict
    escalation_triggered: bool
    escalation_results: Dict[str, List[Any]]
    risk_signals: List[str]

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
    
    queries = {
        "promoter_risk": f"{primary_promoter} NCLT fraud litigation India",
        "credit_history": f"{company_name} credit rating downgrade RBI",
        "sector_outlook": f"{company_name} {industry} sector outlook 2024 2025",
        "mca_check": f"{primary_promoter} MCA director disqualification",
        "default_history": f"{company_name} default NPA bank"
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
    
    triggered = False
    
    # Scan all base search results for keywords
    for category, results_list in state["search_results"].items():
        for result in results_list:
            text_to_check = f"{result['title']} {result['content']}".lower()
            if any(keyword in text_to_check for keyword in keywords_lower):
                logger.warning(f"Escalation triggered by keyword match in {category}: {result['title']}")
                triggered = True
                break
        if triggered:
            break
            
    return {"escalation_triggered": triggered}

def should_escalate(state: ResearchState) -> str:
    if state.get("escalation_triggered", False):
        return "run_escalation_searches"
    return "extract_risk_signals"

async def run_escalation_searches(state: ResearchState) -> ResearchState:
    logger.info("Node: run_escalation_searches")
    tool = TavilySearchTool()
    
    primary_promoter = state["promoter_names"][0] if state["promoter_names"] else "Unknown Promoter"
    company_name = state["company_name"]
    
    queries = {
        "nclt_cases": f"{primary_promoter} NCLT case number status site:nclt.gov.in OR site:ecourts.gov.in",
        "ed_attachments": f"{company_name} enforcement directorate ED attachment"
    }
    
    tasks = [
        tool.search_with_retry(query, retries=2, max_results=3) 
        for query in queries.values()
    ]
    
    results_list = await asyncio.gather(*tasks)
    
    dict_results = {}
    for key, r_list in zip(queries.keys(), results_list):
        dict_results[key] = [r.model_dump() for r in r_list]
        
    return {"escalation_results": dict_results}

async def extract_risk_signals(state: ResearchState) -> ResearchState:
    logger.info("Node: extract_risk_signals")
    # A simple mock extraction for now. In reality, we'd pass all `search_results`
    # and `escalation_results` to an LLM like Anthropic to generate these signals.
    
    signals = []
    if state.get("escalation_triggered", False):
        signals.append("Automated escalation was triggered due to negative keywords found in base search.")
        
        # Check escalation results specifically
        if "escalation_results" in state:
            for cat, results in state["escalation_results"].items():
                if results:
                    signals.append(f"Found deep records in {cat}.")
            
    if not signals:
        signals.append("No immediate red flags detected.")
        
    return {"risk_signals": signals}

# --- Compile Graph ---
workflow = StateGraph(ResearchState)

workflow.add_node("run_base_searches", run_base_searches)
workflow.add_node("check_escalation", check_escalation)
workflow.add_node("run_escalation_searches", run_escalation_searches)
workflow.add_node("extract_risk_signals", extract_risk_signals)

workflow.set_entry_point("run_base_searches")
workflow.add_edge("run_base_searches", "check_escalation")
workflow.add_conditional_edges("check_escalation", should_escalate)
workflow.add_edge("run_escalation_searches", "extract_risk_signals")
workflow.add_edge("extract_risk_signals", END)

research_graph = workflow.compile()

@app.post("/research", response_model=ResearchResponse)
async def start_research(request: ResearchRequest):
    job_id = str(uuid.uuid4())
    
    # Store the job in memory
    jobs[job_id] = {
        "status": "queued",
        "request_data": request.model_dump(),
        "result": None
    }
    
    # Normally we would kick off an async background task here
    
    return ResearchResponse(job_id=job_id, status="queued")

@app.get("/research/{job_id}", response_model=JobStatusResponse)
async def get_research_status(job_id: str):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job_data = jobs[job_id]
    return JobStatusResponse(
        job_id=job_id,
        status=job_data["status"],
        result=job_data["result"]
    )

if __name__ == "__main__":
    async def test():
        print("\n--- Testing LangGraph Agent ---")
        
        company = "Reliance Industries"
        promoters = ["Mukesh Ambani"]
        industry = "Energy and Telecom"
        
        initial_state = {
            "company_name": company,
            "promoter_names": promoters,
            "industry": industry,
            "search_results": {},
            "escalation_triggered": False,
            "escalation_results": {},
            "risk_signals": []
        }
        
        final_state = await research_graph.ainvoke(initial_state)
        
        print(f"\nEscalation Triggered: {final_state['escalation_triggered']}")
        print("\nRisk Signals:")
        for signal in final_state['risk_signals']:
            print(f"- {signal}")
            
    asyncio.run(test())
