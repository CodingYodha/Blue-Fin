import uuid
import os
import asyncio
import logging
import time
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from tavily import AsyncTavilyClient
from dotenv import load_dotenv

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
        tool = TavilySearchTool()
        print("Testing run_parallel_searches...")
        
        company = "Reliance Industries"
        promoters = ["Mukesh Ambani"]
        industry = "Energy and Telecom"
        
        results_dict = await run_parallel_searches(tool, company, promoters, industry)
        
        for category, search_results in results_dict.items():
            print(f"\n--- Category: {category.upper()} ---")
            if not search_results:
                print("No results found.")
            for i, r in enumerate(search_results):
                print(f"{i+1}. {r.title} (Score: {r.score:.2f})")
                print(f"URL: {r.url}")
            
    asyncio.run(test())
