"""
DeepSeek-OCR integration — vision-language OCR for scanned Indian PDFs.

Architecture doc Section 3.1:
  Standard OCR (Tesseract) fails on Indian financial documents:
    - Merged-cell tables get split incorrectly
    - Devanagari script misread
    - Landscape-rotated balance sheets processed upside-down

  DeepSeek-OCR 2 is a vision-language model that understands semantic layout,
  reconstructs tables as Markdown, and handles mixed Hindi-English headers.

This module receives only the *targeted* pages (selected by page_classifier.py)
and returns structured Markdown text for each.
"""

import base64
import logging
import os
from typing import List

import fitz  # PyMuPDF — used to render page to image
import httpx

from .schemas import OCRPageResult, OCRResult

logger = logging.getLogger("deep_learning.ocr_engine")

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_API_URL = os.getenv(
    "DEEPSEEK_API_URL",
    "https://api.deepseek.com/v1/chat/completions",
)

# System prompt telling DeepSeek to reconstruct tables as Markdown.
OCR_SYSTEM_PROMPT = (
    "You are an expert document OCR system specialised in Indian financial documents. "
    "Extract all text from the provided page image. Reconstruct any tables as proper "
    "Markdown tables with headers. Preserve ₹ symbols, lakh/crore notation, and "
    "mixed Hindi-English column headers exactly as they appear. "
    "If a table spans the full page, output only the Markdown table."
)


async def _render_page_to_base64(file_path: str, page_number: int) -> str:
    """Render a single PDF page to a PNG image and return as base64 string."""
    doc = fitz.open(file_path)
    page = doc[page_number - 1]  # page_number is 1-indexed
    # 2x zoom for better OCR quality
    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
    image_bytes = pix.tobytes("png")
    doc.close()
    return base64.b64encode(image_bytes).decode("utf-8")


async def _call_deepseek_ocr(image_b64: str) -> dict:
    """
    Send a base64-encoded page image to DeepSeek vision API for OCR.

    Returns the raw API response dict.
    """
    if not DEEPSEEK_API_KEY:
        logger.warning("DEEPSEEK_API_KEY not set — returning empty OCR result")
        return {"text": "", "confidence": 0.0, "tables": 0}

    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": OCR_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{image_b64}",
                        },
                    },
                    {
                        "type": "text",
                        "text": (
                            "Extract all text and tables from this scanned "
                            "Indian financial document page. Output as Markdown."
                        ),
                    },
                ],
            },
        ],
        "max_tokens": 4096,
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            DEEPSEEK_API_URL,
            json=payload,
            headers=headers,
        )
        response.raise_for_status()
        data = response.json()

    # Extract text from response
    text = ""
    if "choices" in data and data["choices"]:
        text = data["choices"][0].get("message", {}).get("content", "")

    # Count Markdown table separators as a rough table count
    table_count = text.count("|---")

    return {"text": text, "confidence": 0.85, "tables": table_count}


async def run_ocr(
    file_path: str,
    target_pages: List[int],
) -> OCRResult:
    """
    Run DeepSeek-OCR on the specified pages of a PDF.

    Args:
        file_path:    Absolute path to the PDF file.
        target_pages: 1-indexed page numbers to OCR (from page_classifier).

    Returns:
        OCRResult with Markdown text for each processed page.
    """
    results: List[OCRPageResult] = []

    for page_num in target_pages:
        try:
            image_b64 = await _render_page_to_base64(file_path, page_num)
            ocr_response = await _call_deepseek_ocr(image_b64)

            results.append(
                OCRPageResult(
                    page_number=page_num,
                    markdown_text=ocr_response["text"],
                    confidence=ocr_response["confidence"],
                    tables_detected=ocr_response["tables"],
                )
            )
            logger.info(
                f"OCR page {page_num}: {len(ocr_response['text'])} chars, "
                f"{ocr_response['tables']} tables"
            )

        except Exception as e:
            logger.error(f"OCR failed for page {page_num}: {e}")
            results.append(
                OCRPageResult(
                    page_number=page_num,
                    markdown_text="",
                    confidence=0.0,
                    tables_detected=0,
                )
            )

    ocr_result = OCRResult(pages_processed=len(results), results=results)
    logger.info(f"OCR complete: {ocr_result.pages_processed} pages processed")
    return ocr_result
