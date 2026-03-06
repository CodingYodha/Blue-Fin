"""
RAG API Routes — FastAPI endpoints for the RAG pipeline.

=============================================================================
Prefix: /api/v1/rag
Tag: RAG

Endpoints:
  POST   /ingest                → trigger chunk embedding + Qdrant storage
  GET    /ingest-status/{job_id}→ poll ingestion completion
  POST   /extract               → trigger Claude structured extraction
  GET    /extraction/{job_id}   → get extraction results
  POST   /query                 → ad-hoc semantic search (synchronous)
  DELETE /chunks/{job_id}       → delete all vectors for a job
=============================================================================
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

from .ingestor import ingest_all_documents, delete_job_chunks
from .extractor import run_full_extraction
from .retriever import retrieve_chunks
from .schemas import IngestRequest, IngestResult, QueryRequest, RetrievedChunk

from utils import validate_job_id

logger = logging.getLogger("rag.routes")

# Shared volume base path
_BASE_PATH = Path("/tmp/intelli-credit")


# =============================================================================
# Router
# =============================================================================

router = APIRouter(
    prefix="/api/v1/rag",
    tags=["RAG"],
)


# =============================================================================
# Local request model (too simple for schemas.py)
# =============================================================================

class ExtractRequest(BaseModel):
    """POST /api/v1/rag/extract request body."""
    job_id: str

async def _run_ingest_background(
    job_id: str,
    company_name: str,
    doc_types: List[str],
):
    """Background task: ingest chunks and write summary."""
    try:
        results = await ingest_all_documents(job_id, company_name, doc_types)

        # Build summary
        by_doc_type: Dict[str, Any] = {}
        total_stored = 0

        for r in results:
            by_doc_type[r.doc_type] = {
                "chunks": r.chunks_stored,
                "status": r.status,
            }
            if r.error:
                by_doc_type[r.doc_type]["reason"] = r.error
            total_stored += r.chunks_stored

        summary = {
            "status": "ready",
            "job_id": job_id,
            "total_chunks_stored": total_stored,
            "by_doc_type": by_doc_type,
        }

        # Write summary to filesystem
        output_dir = _BASE_PATH / job_id
        output_dir.mkdir(parents=True, exist_ok=True)
        summary_file = output_dir / "rag_ingest_summary.json"
        summary_file.write_text(
            json.dumps(summary, indent=2),
            encoding="utf-8",
        )

        logger.info(
            f"[{job_id}] ✅ Ingest complete: {total_stored} chunks stored → {summary_file}"
        )

    except Exception as e:
        logger.error(f"[{job_id}] Ingest background task failed: {e}")

        # Write error summary
        error_summary = {
            "status": "failed",
            "job_id": job_id,
            "error": "Ingestion failed",
        }
        output_dir = _BASE_PATH / job_id
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "rag_ingest_summary.json").write_text(
            json.dumps(error_summary, indent=2),
            encoding="utf-8",
        )


async def _run_extract_background(job_id: str):
    """Background task: run full Claude extraction."""
    try:
        await run_full_extraction(job_id)
        # run_full_extraction already writes rag_extraction.json
    except Exception as e:
        logger.error(f"[{job_id}] Extract background task failed: {e}")

        # Write error result
        error_result = {
            "status": "failed",
            "job_id": job_id,
            "error": "Extraction failed",
        }
        output_dir = _BASE_PATH / job_id
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "rag_extraction.json").write_text(
            json.dumps(error_result, indent=2),
            encoding="utf-8",
        )


# =============================================================================
# Endpoints
# =============================================================================

@router.post("/ingest")
async def ingest_chunks(
    request: IngestRequest,
    background_tasks: BackgroundTasks,
):
    """
    Trigger chunk embedding + Qdrant storage for a job.

    Called by backend after OCR completes and Go service confirms chunks.json
    is written. Runs ingestion as a background task.
    """
    background_tasks.add_task(
        _run_ingest_background,
        request.job_id,
        request.company_name,
        request.doc_types,
    )

    return {
        "status": "processing",
        "job_id": request.job_id,
        "message": f"RAG ingestion queued for {len(request.doc_types)} document types",
    }


@router.get("/ingest-status/{job_id}")
async def get_ingest_status(job_id: str):
    """
    Poll for ingestion completion.

    Reads rag_ingest_summary.json written by the background ingest task.
    Returns status="processing" while the task is still running.
    """
    validate_job_id(job_id)
    summary_file = _BASE_PATH / job_id / "rag_ingest_summary.json"

    if not summary_file.exists():
        return {"status": "processing", "job_id": job_id}

    try:
        data = json.loads(summary_file.read_text(encoding="utf-8"))
        return data
    except Exception as e:
        logger.error(f"[{job_id}] Failed to read ingest summary: {e}")
        raise HTTPException(status_code=500, detail="Failed to read ingest summary")


@router.post("/extract")
async def extract_from_chunks(
    request: ExtractRequest,
    background_tasks: BackgroundTasks,
):
    """
    Trigger full Claude structured extraction from RAG-retrieved chunks.

    Called by backend after ingestion completes. Runs all 4 extraction
    functions and writes rag_extraction.json.
    """
    background_tasks.add_task(
        _run_extract_background,
        request.job_id,
    )

    return {
        "status": "processing",
        "job_id": request.job_id,
        "message": "RAG extraction queued",
    }


@router.get("/extraction/{job_id}")
async def get_extraction_result(job_id: str):
    """
    Returns the full Claude extraction result.

    The ML scoring pipeline reads this. Returns the contents of
    rag_extraction.json written by the extract background task.
    """
    validate_job_id(job_id)
    extraction_file = _BASE_PATH / job_id / "rag_extraction.json"

    if not extraction_file.exists():
        return {"status": "processing", "job_id": job_id}

    try:
        data = json.loads(extraction_file.read_text(encoding="utf-8"))
        return data
    except Exception as e:
        logger.error(f"[{job_id}] Failed to read extraction result: {e}")
        raise HTTPException(status_code=500, detail="Failed to read extraction result")


@router.post("/query")
async def semantic_query(request: QueryRequest):
    """
    Ad-hoc semantic search — synchronous, returns immediately.

    Used by the CAM Generator (Section 8) to pull source evidence for
    every claim it makes, enabling the full audit trail requirement.
    """
    try:
        chunks = await retrieve_chunks(
            query=request.query,
            job_id=request.job_id,
            top_k=request.top_k,
            doc_type_filter=request.doc_type_filter,
        )

        results = [
            {
                "chunk_text": c.chunk_text,
                "score": round(c.score, 4),
                "page_num": c.page_num,
                "section_name": c.section_name,
                "doc_type": c.doc_type,
                "source_file": c.source_file,
            }
            for c in chunks
        ]

        return {
            "job_id": request.job_id,
            "query": request.query,
            "results": results,
            "result_count": len(results),
        }

    except Exception as e:
        logger.error(f"Semantic query failed: {e}")
        raise HTTPException(status_code=500, detail="Semantic query failed")


@router.delete("/chunks/{job_id}")
async def delete_chunks(job_id: str):
    """
    Delete all Qdrant vectors for a job.

    Used for cleanup or re-processing. Also removes the ingest summary
    and extraction result files.
    """
    validate_job_id(job_id)
    try:
        points_deleted = await delete_job_chunks(job_id)

        # Clean up summary files
        summary_file = _BASE_PATH / job_id / "rag_ingest_summary.json"
        extraction_file = _BASE_PATH / job_id / "rag_extraction.json"

        for f in (summary_file, extraction_file):
            if f.exists():
                f.unlink()

        return {
            "status": "deleted",
            "job_id": job_id,
            "points_deleted": points_deleted,
        }

    except Exception as e:
        logger.error(f"[{job_id}] Chunk deletion failed: {e}")
        raise HTTPException(status_code=500, detail=f"Chunk deletion failed: {e}")
