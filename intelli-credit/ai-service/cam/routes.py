import json
import logging
import os
from pathlib import Path
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, ConfigDict
from supabase import create_client, Client

from .officer_notes import process_officer_notes, OfficerNotesResult

from utils import validate_job_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/cam", tags=["CAM Generator"])

# Supabase Initialization
# The prompt implies a live Supabase client being passed asynchronously
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")
supabase_client = None

if SUPABASE_URL and SUPABASE_KEY:
    try:
        supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)
        logger.info("Supabase client successfully initialized for CAM Officer Notes audit.")
    except Exception as e:
        logger.warning(f"Failed to initialize Supabase client: {e}")
else:
    logger.warning("Supabase URL or Key missing. Officer notes audit logging will be skipped.")

class OfficerNotesRequest(BaseModel):
    job_id: str
    notes_text: str
    officer_id: str

@router.post("/officer-notes", response_model=OfficerNotesResult)
async def post_officer_notes(request: OfficerNotesRequest):
    """
    Accepts Credit Officer field visit notes.
    Runs immediately through injection detection & scoring adjustments.
    """
    validate_job_id(request.job_id)
    job_dir = Path(f"/tmp/intelli-credit/{request.job_id}")
    scoring_file = job_dir / "scoring_result.json"
    
    current_scores = {}
    if scoring_file.exists():
        try:
            with open(scoring_file, "r") as f:
                current_scores = json.load(f)
        except Exception as e:
            logger.error(f"Failed to read scoring result for job {request.job_id}: {e}")
            raise HTTPException(status_code=500, detail="Failed to load existing scoring outputs.")
    else:
        logger.warning(f"No existing ML scores found for job {request.job_id}. Proceeding with base zero scores.")
        
    try:
        result = await process_officer_notes(
            job_id=request.job_id,
            notes_text=request.notes_text,
            officer_id=request.officer_id,
            current_scores=current_scores,
            supabase_client=supabase_client
        )
        return result
        
    except Exception as e:
        logger.error(f"Error processing officer notes: {e}")
        raise HTTPException(status_code=500, detail="Failed to process officer notes.")

class CAMJobRequest(BaseModel):
    job_id: str

@router.post("/generate")
async def process_cam_document(request: CAMJobRequest, background_tasks: BackgroundTasks):
    from .cam_assembler import generate_cam_pipeline
    background_tasks.add_task(generate_cam_pipeline, request.job_id)
    return {"status": "processing", "job_id": request.job_id}

@router.post("/regenerate")
async def regenerate_cam_document(request: CAMJobRequest, background_tasks: BackgroundTasks):
    from .cam_assembler import generate_cam_pipeline
    background_tasks.add_task(generate_cam_pipeline, request.job_id)
    return {"status": "processing", "job_id": request.job_id}

@router.get("/result/{job_id}")
async def fetch_cam_result(job_id: str):
    validate_job_id(job_id)
    draft_path = Path(f"/tmp/intelli-credit/{job_id}/cam_draft.json")
    if not draft_path.exists():
        return {"status": "processing", "job_id": job_id}
        
    try:
        with open(draft_path, "r") as f:
            data = json.load(f)
        return {
            "status": "ready",
            "job_id": job_id,
            "result": data,
            "download_urls": {
                "docx": f"/api/v1/cam/download/{job_id}/docx",
                "pdf": f"/api/v1/cam/download/{job_id}/pdf"
            }
        }
    except Exception as e:
        logger.error(f"Failed to read CAM draft {job_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to parse drafted CAM outputs.")

from fastapi.responses import FileResponse

@router.get("/download/{job_id}/{format}")
async def fetch_cam_downloads(job_id: str, format: str):
    validate_job_id(job_id)
    format = format.lower()
    if format not in ["docx", "pdf"]:
        raise HTTPException(status_code=400, detail="Valid formats are 'docx' or 'pdf'")
        
    file_path = Path(f"/tmp/intelli-credit/{job_id}/cam_final.{format}")
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"The {format.upper()} document is not yet available or failed translation.")
        
    return FileResponse(path=file_path, filename=f"{job_id}_Credit_Memo.{format}")
