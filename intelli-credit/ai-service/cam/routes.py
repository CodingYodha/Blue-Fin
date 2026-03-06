import json
import logging
import os
from pathlib import Path
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict
from supabase import create_client, Client

from .officer_notes import process_officer_notes, OfficerNotesResult

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
        raise HTTPException(status_code=500, detail=str(e))
