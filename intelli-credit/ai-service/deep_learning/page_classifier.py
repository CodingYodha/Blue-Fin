"""
Smart Page Targeting — PyMuPDF-based page classifier.

Architecture doc Section 2 / V6 fix:
  Instead of sending entire PDFs to DeepSeek-OCR (3B+ param model),
  classify each page first:
    1. Text-rich (PyMuPDF extracts >200 chars)  → skip OCR
    2. Scanned  (PyMuPDF extracts <50 chars)    → candidate for OCR
    3. Blank    (0 chars)                        → skip entirely

  Among scanned pages, only those adjacent to financial keywords
  ('Balance Sheet', 'Profit', 'GSTR', 'Turnover', etc.) are sent to OCR.
  This reduces a 100-page PDF from 15-20 min OCR to 15-30 seconds.
"""

import logging
from typing import List

import fitz  # PyMuPDF

from .schemas import (
    PageClassification,
    PageClassificationResult,
    PageType,
)

logger = logging.getLogger("deep_learning.page_classifier")

# Keywords that indicate a page contains critical financial tables.
# When a scanned page is adjacent to (or contains fragments of) these keywords,
# it is prioritised for OCR.
FINANCIAL_KEYWORDS = [
    "balance sheet",
    "profit and loss",
    "profit & loss",
    "p&l",
    "cash flow",
    "schedule of",
    "notes to accounts",
    "gstr",
    "turnover",
    "revenue from operations",
    "related party",
    "contingent liabilities",
    "auditor",
    "debt service",
    "secured loans",
    "unsecured loans",
    "borrowings",
    "net worth",
]

# Thresholds (from V6 hardening)
TEXT_RICH_THRESHOLD = 200   # chars
SCANNED_THRESHOLD = 50      # chars


async def classify_pages(file_path: str) -> PageClassificationResult:
    """
    Open a PDF with PyMuPDF, classify every page, and decide which
    scanned pages should be sent to DeepSeek-OCR.

    Returns a PageClassificationResult with per-page detail and
    the final list of page numbers targeted for OCR.
    """
    doc = fitz.open(file_path)
    pages: List[PageClassification] = []

    text_rich_count = 0
    scanned_count = 0
    blank_count = 0
    ocr_targets: List[int] = []

    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text("text") or ""
        char_count = len(text.strip())

        # --- classify ---
        if char_count == 0:
            page_type = PageType.BLANK
            blank_count += 1
        elif char_count < SCANNED_THRESHOLD:
            page_type = PageType.SCANNED
            scanned_count += 1
        else:
            page_type = PageType.TEXT_RICH
            text_rich_count += 1

        # --- keyword check (case-insensitive) ---
        text_lower = text.lower()
        has_keywords = any(kw in text_lower for kw in FINANCIAL_KEYWORDS)

        # --- decide whether to send to OCR ---
        # Scanned pages with financial keywords (or adjacent to them) go to OCR.
        send_to_ocr = page_type == PageType.SCANNED and has_keywords

        pages.append(
            PageClassification(
                page_number=page_num + 1,   # 1-indexed for human readability
                page_type=page_type,
                text_char_count=char_count,
                has_financial_keywords=has_keywords,
                send_to_ocr=send_to_ocr,
            )
        )

    doc.close()

    # Second pass: also send scanned pages that are *adjacent* to a keyword page
    # (financial tables often span across consecutive scanned pages).
    keyword_page_indices = {
        i for i, p in enumerate(pages) if p.has_financial_keywords
    }
    for i, p in enumerate(pages):
        if (
            p.page_type == PageType.SCANNED
            and not p.send_to_ocr
            and (i - 1 in keyword_page_indices or i + 1 in keyword_page_indices)
        ):
            pages[i] = p.model_copy(update={"send_to_ocr": True})

    ocr_targets = [p.page_number for p in pages if p.send_to_ocr]

    result = PageClassificationResult(
        total_pages=len(pages),
        text_rich_pages=text_rich_count,
        scanned_pages=scanned_count,
        blank_pages=blank_count,
        ocr_target_pages=ocr_targets,
        pages=pages,
    )

    logger.info(
        f"Page classification complete: {result.total_pages} pages — "
        f"{text_rich_count} text-rich, {scanned_count} scanned, "
        f"{blank_count} blank, {len(ocr_targets)} targeted for OCR"
    )

    return result
