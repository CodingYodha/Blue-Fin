"""
Intelli-Credit AI Service — FastAPI Application.

Endpoints:
  POST /api/v1/process-document   → accepts a document processing job
  GET  /api/v1/status/{job_id}    → polls job status / retrieves result
  GET  /health                    → liveness probe (includes Neo4j + Qdrant status)
"""

import json
import logging
from contextlib import asynccontextmanager
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
from entity_graph import (
    create_constraints,
    close_driver,
    neo4j_health_check,
)
from entity_graph.routes import router as entity_graph_router
from rag import (
    ensure_collection_exists,
    qdrant_health_check,
)
from rag.qdrant_client import close_client as close_qdrant

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
# Lifespan — startup / shutdown hooks
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI lifespan context manager.
    Startup: apply Neo4j constraints, ensure Qdrant collection.
    Shutdown: close Neo4j driver, close Qdrant client.
    """
    # Startup
    logger.info("Starting AI Service...")
    try:
        create_constraints()
        logger.info("Neo4j constraints applied at startup")
    except Exception as e:
        logger.warning(f"Neo4j startup failed (will retry on first request): {e}")

    try:
        ensure_collection_exists()
        logger.info("Qdrant collection verified at startup")
    except Exception as e:
        logger.warning(f"Qdrant startup failed (will retry on first request): {e}")

    yield

    # Shutdown
    logger.info("Shutting down AI Service...")
    close_driver()
    close_qdrant()


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Intelli-Credit AI Service",
    description="OCR, page classification, structured extraction, and entity graph for Indian financial documents.",
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include entity graph router
app.include_router(entity_graph_router)

# Shared volume base path (Docker mount)
BASE_PATH = Path("/tmp/intelli-credit")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
async def health_check():
    """Liveness probe — includes Neo4j and Qdrant connectivity status."""
    neo4j_ok = neo4j_health_check()
    qdrant_ok = qdrant_health_check()
    all_ok = neo4j_ok and qdrant_ok
    return {
        "status": "ok" if all_ok else "degraded",
        "services": {
            "ai_service": True,
            "neo4j": neo4j_ok,
            "qdrant": qdrant_ok,
        },
    }


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
