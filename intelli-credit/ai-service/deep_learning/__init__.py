"""
Deep Learning module — Document Intelligence for Intelli-Credit.

Sub-modules:
  - page_classifier : PyMuPDF smart page targeting (V6 fix)
  - ocr_engine      : DeepSeek-VL2 local OCR for scanned pages
  - info_extractor  : Claude-based structured financial + entity extraction
  - schemas         : Pydantic v2 models for all I/O

Orchestrator:
  - process_document() : wires all sub-modules into a single pipeline
"""

import json
import logging
import time
from pathlib import Path

from .schemas import (
    DocumentProcessingResult,
    JobStatusResponse,
    PageClassificationResult,
    ProcessDocumentRequest,
    ProcessDocumentResponse,
)

logger = logging.getLogger("deep_learning")

# Shared volume base path (Docker mount)
_BASE_PATH = Path("/tmp/intelli-credit")


async def process_document(
    job_id: str,
    file_path: str,
    doc_type: str,
) -> DocumentProcessingResult:
    """
    Full document processing pipeline — wires all sub-modules together.

    Pipeline:
      1. classify_pages()        → PageClassificationResult
      2. ocr_document()          → Dict[int, OCRPageResult]  (if needed)
      3. merge_document_text()   → MergedDocument  (writes extracted.txt)
      4. extract_financial_ratios() + extract_entities()  (parallel, if applicable)
      5. Write ocr_output.json   → DocumentProcessingResult

    Error handling:
      - page_classifier fails  → status="failed", errors populated
      - OCR fails on all pages → status="partial", continue with digital text only
      - Claude extraction fails → financial/entity=None, status="partial"
      - NEVER raises unhandled exceptions — always writes a result to disk

    Args:
        job_id:    Unique job identifier from the orchestrator.
        file_path: Absolute path to the PDF file.
        doc_type:  One of "annual_report", "bank_statement", "gst_filing",
                   "rating_report", "legal_notice".

    Returns:
        DocumentProcessingResult (also written to ocr_output.json).
    """
    from .page_classifier import classify_pages
    from .ocr_engine import ocr_document, merge_document_text
    from .info_extractor import extract_financial_ratios, extract_entities

    output_dir = _BASE_PATH / job_id
    output_file = output_dir / "ocr_output.json"
    errors: list[str] = []
    pipeline_start = time.time()

    # Defaults for a failed result
    classification = PageClassificationResult(total_pages=0)
    financial_extraction = None
    entity_extraction = None
    extracted_text_path = ""

    try:
        output_dir.mkdir(parents=True, exist_ok=True)

        # ── Step 1: Classify pages ──────────────────────────────────────
        logger.info(f"[{job_id}] Step 1/4 — Classifying pages: {file_path}")
        try:
            classification = await classify_pages(file_path, doc_type)
        except Exception as e:
            logger.error(f"[{job_id}] Page classification failed: {e}")
            errors.append(f"Page classification failed: {e}")
            return _write_result(
                output_file, job_id, doc_type, "failed",
                classification, None, None, "",
                time.time() - pipeline_start, errors,
            )

        # Bail early if encrypted
        if classification.encrypted:
            errors.append(f"Encrypted PDF: {classification.encryption_error}")
            return _write_result(
                output_file, job_id, doc_type, "failed",
                classification, None, None, "",
                time.time() - pipeline_start, errors,
            )

        # ── Step 2: OCR scanned pages ───────────────────────────────────
        ocr_results = {}
        if classification.ocr_priority_pages:
            logger.info(
                f"[{job_id}] Step 2/4 — OCR on "
                f"{classification.estimated_ocr_pages} pages"
            )
            try:
                ocr_results = await ocr_document(
                    file_path, classification.ocr_priority_pages, doc_type
                )

                # Track per-page OCR failures
                failed_pages = [
                    pn for pn, r in ocr_results.items()
                    if r.confidence == "FAILED"
                ]
                if failed_pages:
                    errors.append(
                        f"OCR failed on pages: {failed_pages}"
                    )

                # If ALL OCR pages failed, log but continue with digital text
                if len(failed_pages) == len(ocr_results):
                    logger.warning(
                        f"[{job_id}] All OCR pages failed — "
                        f"continuing with digital text only"
                    )
                    errors.append("All OCR pages failed. Using digital text only.")

            except Exception as e:
                logger.error(f"[{job_id}] OCR engine failed: {e}")
                errors.append(f"OCR engine failed: {e}")
                # Continue with digital text only — don't abort
        else:
            logger.info(f"[{job_id}] Step 2/4 — No pages need OCR (skipping)")

        # ── Step 3: Merge text ──────────────────────────────────────────
        logger.info(f"[{job_id}] Step 3/4 — Merging document text")
        merged = merge_document_text(
            digital_text=classification.digital_text,
            ocr_results=ocr_results,
            total_pages=classification.total_pages,
            job_id=job_id,
        )
        extracted_text_path = str(output_dir / "extracted.txt")

        # ── Step 4: Claude extraction ───────────────────────────────────
        extraction_doc_types = [
            "annual_report", "gst_filing", "rating_report",
        ]

        if doc_type in extraction_doc_types and merged.full_text.strip():
            logger.info(
                f"[{job_id}] Step 4/4 — Claude extraction "
                f"(financial + entity in parallel)"
            )

            import asyncio

            # Run both Claude calls in parallel
            fin_task = extract_financial_ratios(merged.full_text, doc_type)
            ent_task = extract_entities(merged.full_text, doc_type)

            # Gather with return_exceptions=True so one failure
            # doesn't kill the other
            results = await asyncio.gather(
                fin_task, ent_task, return_exceptions=True
            )

            # Financial extraction
            if isinstance(results[0], Exception):
                logger.error(
                    f"[{job_id}] Financial extraction failed: {results[0]}"
                )
                errors.append(f"Financial extraction failed: {results[0]}")
            else:
                financial_extraction = results[0]

            # Entity extraction
            if isinstance(results[1], Exception):
                logger.error(
                    f"[{job_id}] Entity extraction failed: {results[1]}"
                )
                errors.append(f"Entity extraction failed: {results[1]}")
            else:
                entity_extraction = results[1]
        else:
            logger.info(
                f"[{job_id}] Step 4/4 — Skipping Claude extraction "
                f"(doc_type={doc_type})"
            )

        # ── Determine final status ──────────────────────────────────────
        if not errors:
            status = "success"
        elif merged.has_ocr_failures or financial_extraction is None:
            status = "partial"
        else:
            status = "partial"

        processing_time = time.time() - pipeline_start

        # ── Write result ────────────────────────────────────────────────
        result = _write_result(
            output_file, job_id, doc_type, status,
            classification, financial_extraction, entity_extraction,
            extracted_text_path, processing_time, errors,
        )

        logger.info(
            f"[{job_id}] ✅ Processing complete → {output_file} "
            f"({processing_time:.1f}s, status={status})"
        )
        return result

    except Exception as e:
        # Catch-all — should never reach here, but safety net
        logger.error(f"[{job_id}] ❌ Unexpected pipeline failure: {e}")
        errors.append(f"Unexpected error: {e}")
        processing_time = time.time() - pipeline_start
        return _write_result(
            output_file, job_id, doc_type, "failed",
            classification, None, None, extracted_text_path,
            processing_time, errors,
        )


def _write_result(
    output_file: Path,
    job_id: str,
    doc_type: str,
    status: str,
    classification,
    financial_extraction,
    entity_extraction,
    extracted_text_path: str,
    processing_time: float,
    errors: list[str],
) -> DocumentProcessingResult:
    """Build a DocumentProcessingResult, write it to disk, and return it."""
    result = DocumentProcessingResult(
        job_id=job_id,
        doc_type=doc_type,
        status=status,
        file_path_extracted_text=extracted_text_path,
        page_classification=classification,
        financial_extraction=financial_extraction,
        entity_extraction=entity_extraction,
        processing_time_seconds=round(processing_time, 2),
        errors=errors,
    )

    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(
        result.model_dump_json(indent=2), encoding="utf-8"
    )
    return result


__all__ = [
    "process_document",
    "ProcessDocumentRequest",
    "ProcessDocumentResponse",
    "JobStatusResponse",
    "DocumentProcessingResult",
]
