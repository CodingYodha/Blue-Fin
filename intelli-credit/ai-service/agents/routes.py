import json
from pathlib import Path
from fastapi import APIRouter, BackgroundTasks, HTTPException
from typing import Optional, List
from pydantic import BaseModel

from .research_agent import (
    ResearchRequest,
    execute_research_graph,
    jobs,
    JobStatusResponse
)
from .schemas import RunAgentRequest

from utils import validate_job_id

router = APIRouter(prefix="/api/v1/research-agent", tags=["Research Agent"])

BASE_PATH = Path("/tmp/intelli-credit")

class ResearchAgentRunResponse(BaseModel):
    status: str
    job_id: str
    message: str

@router.post("/run", response_model=ResearchAgentRunResponse)
async def run_research_agent(request: RunAgentRequest, background_tasks: BackgroundTasks):
    validate_job_id(request.job_id)
    job_dir = BASE_PATH / request.job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    
    agent_request = ResearchRequest(
        company_name=request.company_name,
        promoter_names=request.promoter_names,
        industry=request.industry,
        cin=request.cin
    )
    
    # We use the existing async function but wrap it to write the files when done
    async def run_and_save():
        await execute_research_graph(request.job_id, agent_request)
        
        if request.job_id in jobs:
            job_data = jobs[request.job_id]
            # Write full output
            output_file = job_dir / "research_agent_output.json"
            output_file.write_text(json.dumps(job_data, indent=2), encoding="utf-8")
            
            # Write slim summary if completed successfully
            if job_data.get("status") == "completed" and "result" in job_data:
                # Based on requirements, summary is just classification + sentiment
                summary_data = {
                    "status": "ready",
                    "job_id": request.job_id,
                }
                result = job_data["result"]
                summary_data.update(result) # merge promoter_risk, litigation_risk, sector_sentiment_score, etc.
                
                # Add missing fields from root level if present
                if "risk_signals" in job_data:
                    summary_data["raw_risk_signals"] = job_data["risk_signals"]
                
                summary_file = job_dir / "research_agent_summary.json"
                summary_file.write_text(json.dumps(summary_data, indent=2), encoding="utf-8")
            else:
                summary_data = {
                    "status": job_data.get("status", "failed"),
                    "job_id": request.job_id,
                    "error": job_data.get("result", {}).get("error", "Unknown error")
                }
                summary_file = job_dir / "research_agent_summary.json"
                summary_file.write_text(json.dumps(summary_data, indent=2), encoding="utf-8")

    background_tasks.add_task(run_and_save)
    
    return ResearchAgentRunResponse(
        status="processing",
        job_id=request.job_id,
        message="Research agent started"
    )

@router.get("/status/{job_id}")
async def get_research_status(job_id: str):
    validate_job_id(job_id)
    summary_file = BASE_PATH / job_id / "research_agent_summary.json"
    
    if summary_file.exists():
        try:
            raw = summary_file.read_text(encoding="utf-8")
            return json.loads(raw)
        except Exception as e:
            return {"status": "failed", "error": "Failed to read summary"}
            
    # Check in-memory jobs as fallback or if still processing
    if job_id in jobs:
        status = jobs[job_id].get("status")
        if status in ["queued", "running"]:
            return {"status": "processing"}
        elif status == "failed":
            return {"status": "failed", "error": jobs[job_id].get("result", {}).get("error", "Unknown error")}
            
    return {"status": "processing"}
