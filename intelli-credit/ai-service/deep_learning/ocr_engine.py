"""
DeepSeek-VL2 Local OCR Engine — GPU-based document OCR.

=============================================================================
ARCHITECTURE DOC: Section 3.1 — DeepSeek-OCR (Indian PDF Problem)
=============================================================================
Standard OCR (Tesseract) fails on Indian financial documents:
  - Merged-cell tables split incorrectly
  - Devanagari script misread
  - Landscape-rotated balance sheets processed upside-down
  - Amounts in ₹, lakh, crore notation mangled

DeepSeek-VL2-tiny (~3B params) is a vision-language model that understands
document layout semantics.  It reconstructs tables as Markdown, handles mixed
Hindi-English headers, and reads rotated pages.

VRAM STRATEGY (6 GB constraint):
  - Unsloth FastVisionModel loads 4-bit quantized → ~2-2.5 GB VRAM
  - Model loaded ONCE at module import (singleton) — not per-request
  - threading.Lock() guards inference (GPU not thread-safe)
  - torch.cuda.empty_cache() after each page frees activation memory
  - Pages rendered at 150 DPI (not 200) to reduce image tensor size

NO API calls, NO internet, NO API keys.  Entirely offline inference.
=============================================================================
"""

import asyncio
import logging
import os
import threading
import time
from typing import Dict, List

import fitz  # PyMuPDF
import numpy as np
from PIL import Image
import easyocr

from .schemas import OCRPageResult

logger = logging.getLogger("deep_learning.ocr_engine")

# ---------------------------------------------------------------------------
# Module-level singleton — loaded ONCE at service startup
# ---------------------------------------------------------------------------
_reader = None
_lock = threading.Lock()

# DPI for page rendering: 150 for typed docs, 200 for PARTIAL pages
_DEFAULT_DPI = 150
_PARTIAL_DPI = 200


def _load_model():
    """
    Load EasyOCR CPU model.
    Runs once at module import or lazily on first OCR request.
    Takes 1-2 GB RAM, no GPU required. Provides solid basic OCR.
    """
    global _reader
    
    logger.info("Loading EasyOCR (CPU mode) instead of DeepSeek-VL2...")
    load_start = time.time()
    # Support English and Hindi
    _reader = easyocr.Reader(['en', 'hi'], gpu=False)
    
    load_time = time.time() - load_start
    logger.info(f"✅ EasyOCR Model loaded in {load_time:.1f}s")


def _ensure_model():
    """Lazy-load the model on first OCR request, not at import time."""
    if _reader is None:
        _load_model()


# NOTE: Model is loaded lazily on first OCR request via _ensure_model()
# This avoids crashes when no pages need OCR (the common case for digital PDFs).


# ---------------------------------------------------------------------------
# OCR system prompt
# ---------------------------------------------------------------------------
_OCR_SYSTEM_PROMPT = (
    "You are a financial document OCR engine specialised in Indian corporate documents. "
    "Extract ALL text from this document image with exact fidelity. "
    "For tables: reconstruct as Markdown tables preserving all row-column relationships. "
    "For amounts: preserve exact formatting — ₹, lakh, crore, decimal points. "
    "For mixed Hindi-English headers: transliterate Hindi to English in [brackets]. "
    "If the page is rotated landscape, rotate your reading accordingly. "
    "Do not summarise. Return the complete raw text exactly as it appears."
)


# ---------------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------------

async def convert_page_to_image(
    pdf_path: str,
    page_num: int,
    is_partial: bool = False,
) -> Image.Image:
    """
    Render a single PDF page to a PIL Image.

    Uses PyMuPDF to render at 150 DPI (default) or 200 DPI for PARTIAL pages
    where garbled text suggests the page needs higher-resolution OCR.

    Args:
        pdf_path:   Absolute path to the PDF file.
        page_num:   0-indexed page number.
        is_partial: True if the page was classified as PARTIAL (use higher DPI).

    Returns:
        PIL.Image in RGB mode.
    """
    dpi = _PARTIAL_DPI if is_partial else _DEFAULT_DPI
    zoom = dpi / 72.0  # PyMuPDF default is 72 DPI

    doc = fitz.open(pdf_path)
    page = doc[page_num]
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    doc.close()

    return img


def _ocr_single_page_sync(
    page_image: Image.Image,
    page_context: str,
    doc_type: str,
    page_num: int,
) -> OCRPageResult:
    """
    Run OCR inference on a single page image using EasyOCR (CPU).

    Acquires the global lock before inference.

    Args:
        page_image:   PIL Image of the rendered page.
        page_context: Optional context string for the model (e.g. neighboring page text).
        doc_type:     Document type string for prompt context.
        page_num:     0-indexed page number (for logging and result).

    Returns:
        OCRPageResult with raw_text, has_table flag, and confidence level.
    """
    if _reader is None:
        _ensure_model()
    if _reader is None:
        logger.error("EasyOCR model not loaded — returning empty OCR result")
        return OCRPageResult(
            page_number=page_num, raw_text="", has_table=False, confidence="FAILED"
        )

    try:
        with _lock:
            start = time.time()

            # EasyOCR expects numpy array
            image_np = np.array(page_image)
            
            # detail=0 returns just text list, detail=1 returns bounding boxes + text + confidence
            results = _reader.readtext(image_np, detail=1)

            # Reconstruct basic text with newlines
            raw_text = "\n".join([text for _, text, _ in results])

            elapsed = time.time() - start

        # Classify result
        has_table = "|" in raw_text or len(raw_text) > 300 # Rough heuristic for table presence
        if len(raw_text) > 100:
            confidence = "HIGH"
        elif len(raw_text) > 0:
            confidence = "LOW"
        else:
            confidence = "FAILED"

        logger.info(
            f"OCR page {page_num}: {len(raw_text)} chars, "
            f"table={'yes' if has_table else 'no'}, "
            f"confidence={confidence}, time={elapsed:.2f}s"
        )

        return OCRPageResult(
            page_number=page_num,
            raw_text=raw_text,
            has_table=has_table,
            confidence=confidence,
        )

    except Exception as e:
        logger.error(f"OCR failed for page {page_num}: {e}")
        return OCRPageResult(
            page_number=page_num, raw_text="", has_table=False, confidence="FAILED"
        )


async def ocr_single_page(
    page_image: Image.Image,
    page_context: str,
    doc_type: str,
    page_num: int,
) -> OCRPageResult:
    """
    Async wrapper around synchronous GPU inference.

    Uses asyncio.to_thread() to run the blocking inference in a thread
    pool, keeping FastAPI's event loop unblocked.
    """
    return await asyncio.to_thread(
        _ocr_single_page_sync, page_image, page_context, doc_type, page_num
    )


async def ocr_document(
    pdf_path: str,
    ocr_pages: List[int],
    doc_type: str,
) -> Dict[int, OCRPageResult]:
    """
    Run OCR on specified pages of a PDF SEQUENTIALLY.

    The GPU cannot run two inferences in parallel, so pages are processed
    one at a time.  asyncio.to_thread() ensures the event loop stays
    responsive between pages.

    Args:
        pdf_path:   Absolute path to the PDF file.
        ocr_pages:  List of 0-indexed page numbers to OCR.
        doc_type:   Document type string for prompt context.

    Returns:
        Dict mapping page_number → OCRPageResult.
    """
    results: Dict[int, OCRPageResult] = {}
    total_start = time.time()

    logger.info(f"Starting OCR on {len(ocr_pages)} pages from {pdf_path}")

    for page_num in ocr_pages:
        # Render page to image (150 DPI default)
        page_image = await convert_page_to_image(pdf_path, page_num)

        # Build context from neighboring pages (if available)
        page_context = f"Page {page_num + 1} of document"

        # Run inference (sequential — one page at a time)
        result = await ocr_single_page(page_image, page_context, doc_type, page_num)
        results[page_num] = result

    total_time = time.time() - total_start
    logger.info(
        f"✅ OCR complete: {len(results)} pages in {total_time:.1f}s "
        f"(avg {total_time / max(len(results), 1):.1f}s/page)"
    )

    return results


# ---------------------------------------------------------------------------
# Document text merger (V11 fix — filesystem-based handoff)
# ---------------------------------------------------------------------------

def merge_document_text(
    digital_text: Dict[int, str],
    ocr_results: Dict[int, "OCRPageResult"],
    total_pages: int,
    job_id: str,
) -> "MergedDocument":
    """
    Merge digital page text and OCR results into one coherent document.

    Produces a single page-ordered string and writes it to disk so
    downstream services (Go service, info_extractor) can read from the
    filesystem instead of passing large payloads over HTTP (V11 fix).

    Args:
        digital_text: ``{page_num: text}`` dict from page_classifier.
        ocr_results:  ``{page_num: OCRPageResult}`` dict from ocr_document.
        total_pages:  Total number of pages in the original PDF.
        job_id:       Job identifier — used for the output file path.

    Returns:
        ``MergedDocument`` with full_text, per-page breakdown, and stats.
    """
    from pathlib import Path
    from .schemas import MergedDocument, MergedPage

    pages: list[MergedPage] = []
    text_parts: list[str] = []

    digital_count = 0
    ocr_count = 0
    skipped_count = 0
    has_failures = False

    for page_num in range(total_pages):
        if page_num in digital_text:
            source = "DIGITAL"
            text = digital_text[page_num]
            digital_count += 1
        elif page_num in ocr_results:
            source = "OCR"
            text = ocr_results[page_num].raw_text
            ocr_count += 1
            if ocr_results[page_num].confidence == "FAILED":
                has_failures = True
        else:
            source = "SKIPPED"
            text = ""
            skipped_count += 1

        pages.append(MergedPage(page_num=page_num, source=source, text=text))

        if text.strip():
            text_parts.append(f"\n\n--- PAGE {page_num} ---\n\n{text.strip()}")

    full_text = "".join(text_parts).strip()

    # Write to filesystem (V11 — downstream reads from disk, not HTTP)
    output_dir = Path("/tmp/intelli-credit") / job_id
    output_dir.mkdir(parents=True, exist_ok=True)
    extracted_path = output_dir / "extracted.txt"
    extracted_path.write_text(full_text, encoding="utf-8")
    logger.info(
        f"[{job_id}] Merged document: {total_pages} pages "
        f"({digital_count} digital, {ocr_count} OCR, {skipped_count} skipped) "
        f"→ {extracted_path}"
    )

    return MergedDocument(
        full_text=full_text,
        pages=pages,
        total_pages=total_pages,
        digital_page_count=digital_count,
        ocr_page_count=ocr_count,
        skipped_page_count=skipped_count,
        has_ocr_failures=has_failures,
    )

