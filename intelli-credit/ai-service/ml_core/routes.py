from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel
import os
import json
import logging
from pathlib import Path

from .scorer import run_full_scoring

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/scoring", tags=["ML Scoring"])

BASE_PATH = Path("/tmp/intelli-credit")

class ScoringRunRequest(BaseModel):
    job_id: str

class ScoringRunResponse(BaseModel):
    status: str
    job_id: str
    message: str

def get_job_dir(job_id: str) -> Path:
    return BASE_PATH / job_id

async def execute_background_scoring(job_id: str):
    logger.info(f"Starting ML scoring for job {job_id}")
    try:
        await run_full_scoring(job_id)
        logger.info(f"ML scoring completed for job {job_id}")
    except Exception as e:
        logger.error(f"Error in ML scoring for job {job_id}: {e}")
        # Could write an error state file here if needed:
        error_path = get_job_dir(job_id) / "scoring_error.json"
        with open(error_path, "w") as f:
            json.dump({"job_id": job_id, "error": str(e), "status": "failed"}, f)

@router.post("/run", response_model=ScoringRunResponse)
async def run_scoring(request: ScoringRunRequest, background_tasks: BackgroundTasks):
    job_dir = get_job_dir(request.job_id)
    job_dir.mkdir(parents=True, exist_ok=True)
    
    background_tasks.add_task(execute_background_scoring, request.job_id)
    return ScoringRunResponse(
        status="processing",
        job_id=request.job_id,
        message="ML Scoring inference pipeline started"
    )

@router.get("/result/{job_id}")
async def get_scoring_result(job_id: str):
    job_dir = get_job_dir(job_id)
    result_file = job_dir / "scoring_result.json"
    error_file = job_dir / "scoring_error.json"

    if error_file.exists():
        with open(error_file, "r") as f:
            err = json.load(f)
        return {"status": "failed", "error": err.get("error")}

    if not result_file.exists():
        return {"status": "processing"}

    with open(result_file, "r") as f:
        data = json.load(f)
        
    return {"status": "ready", "result": data}
