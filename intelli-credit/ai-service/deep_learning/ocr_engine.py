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
import torch
from PIL import Image
from unsloth import FastVisionModel

from .schemas import OCRPageResult

logger = logging.getLogger("deep_learning.ocr_engine")

# ---------------------------------------------------------------------------
# Module-level singleton — loaded ONCE at service startup
# ---------------------------------------------------------------------------
_model = None
_tokenizer = None
_lock = threading.Lock()

# DPI for page rendering: 150 for typed docs, 200 for PARTIAL pages
_DEFAULT_DPI = 150
_PARTIAL_DPI = 200


def _load_model():
    """
    Load DeepSeek-VL2-tiny with Unsloth 4-bit quantization.

    Runs once at module import.  Unsloth's FastVisionModel handles:
      - 4-bit quantization (fits in 6 GB VRAM)
      - Optimized CUDA kernels for faster inference
      - ~30% less VRAM than standard bitsandbytes

    Env var DEEPSEEK_MODEL_PATH must point to the HuggingFace model
    directory containing config.json, tokenizer files, and .safetensors.
    """
    global _model, _tokenizer

    model_path = os.environ.get(
        "DEEPSEEK_MODEL_PATH",
        os.path.join(os.path.dirname(__file__), "models", "deepseek-vl2-tiny"),
    )

    if not os.path.isdir(model_path):
        logger.error(
            f"Model directory not found: {model_path}.  "
            f"Set DEEPSEEK_MODEL_PATH or download with: "
            f"huggingface-cli download deepseek-ai/deepseek-vl2-tiny --local-dir {model_path}"
        )
        return

    logger.info(f"Loading DeepSeek-VL2-tiny from {model_path} (4-bit, Unsloth)...")
    load_start = time.time()

    # SECURITY NOTE: trust_remote_code=True is required for DeepSeek-VL2's custom
    # model architecture. Only use with locally downloaded, verified model weights.
    # Never point DEEPSEEK_MODEL_PATH to an untrusted or user-controlled directory.
    _model, _tokenizer = FastVisionModel.from_pretrained(
        model_path,
        load_in_4bit=True,
        dtype=torch.float16,
        trust_remote_code=True,
    )
    FastVisionModel.for_inference(_model)

    load_time = time.time() - load_start
    logger.info(f"✅ Model loaded in {load_time:.1f}s")


# Load at import time — runs once when ai-service starts
_load_model()


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
    Run OCR inference on a single page image (synchronous, GPU-bound).

    Acquires the global lock before inference and releases after.
    Calls torch.cuda.empty_cache() to free activation memory between pages.

    Args:
        page_image:   PIL Image of the rendered page.
        page_context: Optional context string for the model (e.g. neighboring page text).
        doc_type:     Document type string for prompt context.
        page_num:     0-indexed page number (for logging and result).

    Returns:
        OCRPageResult with raw_text, has_table flag, and confidence level.
    """
    if _model is None or _tokenizer is None:
        logger.error("DeepSeek-VL2 model not loaded — returning empty OCR result")
        return OCRPageResult(
            page_number=page_num, raw_text="", has_table=False, confidence="FAILED"
        )

    user_content = (
        f"Document type: {doc_type}. Context: {page_context}\n\n"
        "Extract all text from this page."
    )

    try:
        with _lock:
            start = time.time()

            # Build chat messages in the format DeepSeek-VL2 expects
            messages = [
                {"role": "system", "content": _OCR_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {"type": "image", "image": page_image},
                        {"type": "text", "text": user_content},
                    ],
                },
            ]

            # Apply chat template and tokenize
            input_text = _tokenizer.apply_chat_template(
                messages, add_generation_prompt=True, tokenize=False
            )
            inputs = _tokenizer(
                input_text,
                return_tensors="pt",
                padding=True,
                truncation=True,
            ).to(_model.device)

            # Add image to model inputs if the tokenizer supports it
            if hasattr(_tokenizer, "process_images"):
                image_inputs = _tokenizer.process_images([page_image])
                inputs.update(image_inputs)

            # Greedy decoding — deterministic, faster
            with torch.no_grad():
                output_ids = _model.generate(
                    **inputs,
                    max_new_tokens=2048,
                    do_sample=False,
                )

            # Decode only the new tokens (skip the prompt)
            generated_ids = output_ids[:, inputs["input_ids"].shape[1]:]
            raw_text = _tokenizer.decode(
                generated_ids[0], skip_special_tokens=True
            ).strip()

            elapsed = time.time() - start

            # Free activation memory
            torch.cuda.empty_cache()

        # Classify result
        has_table = "|" in raw_text
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
        torch.cuda.empty_cache()
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

