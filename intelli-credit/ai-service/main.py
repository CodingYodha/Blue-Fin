"""
Intelli-Credit AI Service — FastAPI Application.

Endpoints:
  POST /api/v1/process-document   → accepts a document processing job
  GET  /api/v1/status/{job_id}    → polls job status / retrieves result
  GET  /health                    → liveness probe
"""

import json
import logging
from pathlib import Path

import fitz  # noqa: F401 — ensure PyMuPDF is importable at startup
from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from deep_learning import (
    process_document,
    DocumentProcessingResult,
    JobStatusResponse,
    ProcessDocumentRequest,
    ProcessDocumentResponse,
)

load_dotenv()

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("ai-service")

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Intelli-Credit AI Service",
    description="OCR, page classification, and structured extraction for Indian financial documents.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Shared volume base path (Docker mount)
BASE_PATH = Path("/tmp/intelli-credit")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
async def health_check():
    """Liveness probe."""
    return {"status": "ok"}


@app.post("/api/v1/process-document", response_model=ProcessDocumentResponse)
async def post_process_document(
    request: ProcessDocumentRequest,
    background_tasks: BackgroundTasks,
):
    """
    Accept a document processing job. Returns immediately while
    processing runs in the background via the orchestrator.
    """
    # Validate file exists
    full_path = Path(request.file_path)
    if not full_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"File not found: {request.file_path}",
        )

    # Kick off background pipeline (orchestrator handles all error cases)
    background_tasks.add_task(
        process_document,
        job_id=request.job_id,
        file_path=request.file_path,
        doc_type=request.doc_type,
    )

    return ProcessDocumentResponse(
        status="processing",
        job_id=request.job_id,
        message=f"Document processing started for job {request.job_id}. "
                f"Poll /api/v1/status/{request.job_id} for results.",
    )


@app.get("/api/v1/status/{job_id}", response_model=JobStatusResponse)
async def get_status(job_id: str):
    """
    Poll the status of a processing job. Returns the full result
    JSON once processing is complete, or a processing status if still running.
    """
    output_file = BASE_PATH / job_id / "ocr_output.json"

    if not output_file.exists():
        return JobStatusResponse(
            job_id=job_id,
            status="processing",
        )

    try:
        raw = output_file.read_text(encoding="utf-8")
        data = json.loads(raw)
        result = DocumentProcessingResult(**data)
        return JobStatusResponse(
            job_id=job_id,
            status=result.status,
            result=result,
        )
    except Exception as e:
        logger.error(f"Failed to read output file for {job_id}: {e}")
        return JobStatusResponse(
            job_id=job_id,
            status="failed",
            error=str(e),
        )
