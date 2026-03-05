"""
Intelli-Credit AI Service — FastAPI Application.

Endpoints:
  POST /api/v1/process-document   → accepts a document processing job
  GET  /api/v1/status/{job_id}    → polls job status / retrieves result
  GET  /health                    → liveness probe
"""

import json
import logging
import os
from pathlib import Path

import fitz  # noqa: F401 — ensure PyMuPDF is importable at startup
from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from deep_learning.schemas import (
    DocType,
    DocumentProcessingOutput,
    JobStatusResponse,
    ProcessDocumentRequest,
    ProcessDocumentResponse,
    ProcessingStatus,
)
from deep_learning.page_classifier import classify_pages
from deep_learning.ocr_engine import run_ocr
from deep_learning.info_extractor import extract_structured_info

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
# Background processing pipeline
# ---------------------------------------------------------------------------

async def _process_document(job_id: str, file_path: str, doc_type: DocType):
    """
    Full document processing pipeline (runs in background):
      1. Classify pages  (PyMuPDF)
      2. OCR scanned pages (DeepSeek)
      3. Combine text from all pages
      4. Extract structured info (Claude)
      5. Write result JSON to shared volume
    """
    output_dir = BASE_PATH / job_id
    output_file = output_dir / "ocr_output.json"

    try:
        # Ensure output directory exists
        output_dir.mkdir(parents=True, exist_ok=True)

        # 1. Classify pages
        logger.info(f"[{job_id}] Step 1/4 — Classifying pages: {file_path}")
        classification = await classify_pages(file_path)

        # 2. OCR scanned pages targeted by the classifier
        logger.info(
            f"[{job_id}] Step 2/4 — OCR on {len(classification.ocr_target_pages)} pages"
        )
        ocr_result = await run_ocr(file_path, classification.ocr_target_pages)

        # 3. Combine text: text-rich pages (PyMuPDF direct) + OCR Markdown
        logger.info(f"[{job_id}] Step 3/4 — Combining text")
        combined_text = _combine_page_text(file_path, classification, ocr_result)

        # 4. Structured extraction via Claude
        logger.info(f"[{job_id}] Step 4/4 — Claude structured extraction")
        extraction = await extract_structured_info(
            combined_text=combined_text,
            doc_type=doc_type,
            page_count=classification.total_pages,
        )

        # 5. Build final output and write to disk
        output = DocumentProcessingOutput(
            job_id=job_id,
            status=ProcessingStatus.COMPLETED,
            doc_type=doc_type,
            page_classification=classification,
            ocr_result=ocr_result,
            extraction=extraction,
        )

        output_file.write_text(
            output.model_dump_json(indent=2), encoding="utf-8"
        )
        logger.info(f"[{job_id}] ✅ Processing complete → {output_file}")

    except Exception as e:
        logger.error(f"[{job_id}] ❌ Processing failed: {e}")
        error_output = DocumentProcessingOutput(
            job_id=job_id,
            status=ProcessingStatus.FAILED,
            doc_type=doc_type,
            error=str(e),
        )
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file.write_text(
            error_output.model_dump_json(indent=2), encoding="utf-8"
        )


def _combine_page_text(file_path, classification, ocr_result) -> str:
    """
    Merge text from two sources:
      - Text-rich pages: extracted directly by PyMuPDF (fast, free)
      - OCR pages: Markdown returned by DeepSeek

    Returns a single combined string for Claude extraction.
    """
    import fitz as _fitz

    doc = _fitz.open(file_path)
    parts: list[str] = []

    # Build a lookup for OCR results by page number
    ocr_lookup = {r.page_number: r.markdown_text for r in ocr_result.results}

    for page_info in classification.pages:
        pn = page_info.page_number

        if pn in ocr_lookup and ocr_lookup[pn]:
            # Use OCR output for scanned pages
            parts.append(f"--- Page {pn} (OCR) ---\n{ocr_lookup[pn]}")
        elif page_info.page_type.value == "text_rich":
            # Use PyMuPDF direct extraction
            text = doc[pn - 1].get_text("text") or ""
            if text.strip():
                parts.append(f"--- Page {pn} ---\n{text.strip()}")

    doc.close()
    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
async def health_check():
    """Liveness probe."""
    return {"status": "ok"}


@app.post("/api/v1/process-document", response_model=ProcessDocumentResponse)
async def process_document(
    request: ProcessDocumentRequest,
    background_tasks: BackgroundTasks,
):
    """
    Accept a document processing job. Returns immediately while
    processing runs in the background.
    """
    # Validate file exists
    full_path = Path(request.file_path)
    if not full_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"File not found: {request.file_path}",
        )

    # Kick off background pipeline
    background_tasks.add_task(
        _process_document,
        job_id=request.job_id,
        file_path=request.file_path,
        doc_type=request.doc_type,
    )

    return ProcessDocumentResponse(
        status="processing",
        job_id=request.job_id,
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
            status=ProcessingStatus.PROCESSING,
        )

    try:
        raw = output_file.read_text(encoding="utf-8")
        data = json.loads(raw)
        return JobStatusResponse(
            job_id=job_id,
            status=ProcessingStatus(data.get("status", "completed")),
            result=data,
        )
    except Exception as e:
        logger.error(f"Failed to read output file for {job_id}: {e}")
        return JobStatusResponse(
            job_id=job_id,
            status=ProcessingStatus.FAILED,
            error=str(e),
        )
