"""
Smart Page Targeting — PyMuPDF-based page classifier (V6 fix).

=============================================================================
ARCHITECTURE DOC: Section 2 / Vulnerability V6
=============================================================================
DeepSeek-OCR 2 is a 3B+ parameter vision-language model.  Processing a
100-page scanned document takes 15-20 minutes.  The V6 fix uses PyMuPDF
(fitz) to scan every page cheaply first (zero cost, milliseconds) and
only routes pages that are BOTH scanned AND financially relevant to the
expensive OCR model.

RESULT: 100-page PDF → typically 3-6 pages sent to OCR → 15-30 seconds
instead of 15-20 minutes.

Classification thresholds:
  >200 chars  → DIGITAL   (born-digital, PyMuPDF text is sufficient)
  50-200 chars → PARTIAL   (maybe OCR-useful, lower priority)
  <50 chars   → SCANNED   (image-based, needs OCR)
  0 chars     → BLANK     (skip)

OCR targeting heuristic:
  For SCANNED/PARTIAL pages, check if financial keywords appear on:
    (a) the page itself (even garbled text may contain fragments)
    (b) the immediately preceding page
    (c) the immediately following page
  If yes → OCR_PRIORITY.  If no → OCR_SKIP.

Doc-type overrides:
  bank_statement → no OCR needed (digital CSVs)
  gst_filing     → all SCANNED pages become OCR_PRIORITY (every page matters)

=============================================================================
"""

import logging
from typing import Dict, List, Optional, Tuple

import fitz  # PyMuPDF

from thefuzz import fuzz

from .schemas import (
    PageClassification,
    PageClassificationResult,
)

logger = logging.getLogger("deep_learning.page_classifier")

# ---------------------------------------------------------------------------
# Financial keyword list
# Covers terms from Balance Sheet, P&L, GST filings, audit notes, and
# corporate governance sections of Indian Annual Reports.
# ---------------------------------------------------------------------------
FINANCIAL_KEYWORDS: List[str] = [
    "Balance Sheet",
    "Profit",
    "Loss",
    "EBITDA",
    "GSTR",
    "Turnover",
    "Revenue",
    "Cash Flow",
    "Borrowings",
    "Debt",
    "DSCR",
    "Equity",
    "Liabilities",
    "Assets",
    "Auditor",
    "Director",
    "Promoter",
    "Related Party",
    "Collateral",
]

# Pre-compute lower-case versions for exact matching
_KEYWORDS_LOWER: List[str] = [kw.lower() for kw in FINANCIAL_KEYWORDS]

# Fuzzy-match threshold (0-100).  80 catches OCR-garbled variants like
# "Balanc Sheet" or "Profi & Loss" while avoiding false positives.
_FUZZY_THRESHOLD: int = 80

# Character-count thresholds for page classification
_DIGITAL_THRESHOLD: int = 200
_SCANNED_THRESHOLD: int = 50


# ---------------------------------------------------------------------------
# Keyword detection (exact + fuzzy)
# ---------------------------------------------------------------------------

def _has_financial_keywords(text: str) -> bool:
    """
    Check whether ``text`` contains any financial keyword.

    Uses a two-stage strategy:
      1. **Exact match** (fast): case-insensitive substring search.
      2. **Fuzzy match** (slower, run only if exact fails): splits text into
         word n-grams and compares each against the keyword list with
         ``thefuzz.fuzz.ratio``.  This catches OCR-garbled fragments like
         "Balanc Sheet" (ratio ≈ 85 vs "Balance Sheet").

    Args:
        text: Raw text extracted from a PDF page by PyMuPDF.

    Returns:
        True if at least one financial keyword is detected.
    """
    text_lower = text.lower()

    # --- Stage 1: exact substring match ---
    for kw in _KEYWORDS_LOWER:
        if kw in text_lower:
            return True

    # --- Stage 2: fuzzy match on word windows ---
    # Only run if the page has some (but garbled) text — i.e. PARTIAL range.
    if len(text_lower) < 10:
        return False

    words = text_lower.split()
    # Build 1-gram, 2-gram, and 3-gram windows to cover multi-word keywords
    for window_size in (1, 2, 3):
        for i in range(len(words) - window_size + 1):
            window = " ".join(words[i : i + window_size])
            for kw in _KEYWORDS_LOWER:
                if fuzz.ratio(window, kw) >= _FUZZY_THRESHOLD:
                    return True

    return False


# ---------------------------------------------------------------------------
# Core classifier
# ---------------------------------------------------------------------------

async def classify_pages(
    pdf_path: str,
    doc_type: str,
) -> PageClassificationResult:
    """
    Classify every page of a PDF and decide which pages need OCR.

    This is the entry point for the V6 smart page targeting pipeline.
    It opens the PDF with PyMuPDF, extracts text from every page at
    near-zero cost, classifies pages by text density, applies a keyword
    heuristic (with fuzzy matching) to select OCR targets, and returns
    all digital text so downstream modules can skip OCR for those pages.

    Args:
        pdf_path: Absolute path to the PDF file.
        doc_type: One of the ``DocType`` enum values as a string
                  (``"annual_report"``, ``"bank_statement"``, etc.).

    Returns:
        ``PageClassificationResult`` containing:
          - ``digital_pages``: 0-indexed page numbers with sufficient text
          - ``ocr_priority_pages``: pages to send to DeepSeek-OCR
          - ``ocr_skip_pages``: scanned but not financially relevant
          - ``digital_text``: ``{page_num: extracted_text}`` for DIGITAL pages
          - ``encrypted``: True if the PDF could not be opened

    Raises:
        No exceptions are raised.  Encrypted PDFs return a result with
        ``encrypted=True`` and an ``encryption_error`` message.
    """

    # --- Handle encrypted PDFs gracefully ---
    try:
        doc = fitz.open(pdf_path)
        if doc.is_encrypted:
            doc.close()
            logger.warning(f"PDF is encrypted: {pdf_path}")
            return PageClassificationResult(
                total_pages=0,
                encrypted=True,
                encryption_error="PDF is encrypted and cannot be processed without a password.",
            )
    except Exception as exc:
        logger.error(f"Failed to open PDF {pdf_path}: {exc}")
        return PageClassificationResult(
            total_pages=0,
            encrypted=True,
            encryption_error=str(exc),
        )

    total = len(doc)
    logger.info(f"Classifying {total} pages from {pdf_path} (doc_type={doc_type})")

    # --- Phase 1: extract text and classify each page ---
    page_texts: List[str] = []
    page_types: List[str] = []  # "digital", "scanned", "partial", "blank"
    keyword_flags: List[bool] = []

    for page_num in range(total):
        raw_text = doc[page_num].get_text("text") or ""
        text = raw_text.strip()
        char_count = len(text)
        page_texts.append(text)

        # Classify by character count
        if char_count == 0:
            page_types.append("blank")
        elif char_count < _SCANNED_THRESHOLD:
            page_types.append("scanned")
        elif char_count <= _DIGITAL_THRESHOLD:
            page_types.append("partial")
        else:
            page_types.append("digital")

        # Check for financial keywords (exact + fuzzy)
        keyword_flags.append(_has_financial_keywords(text))

    doc.close()

    # --- Phase 2: OCR decision per page ---
    pages: List[PageClassification] = []
    digital_pages: List[int] = []
    ocr_priority: List[int] = []
    ocr_skip: List[int] = []
    digital_text: Dict[int, str] = {}

    for i in range(total):
        p_type = page_types[i]
        has_kw = keyword_flags[i]

        # Check neighbors for keywords
        prev_kw = keyword_flags[i - 1] if i > 0 else False
        next_kw = keyword_flags[i + 1] if i < total - 1 else False
        neighbor_kw = prev_kw or next_kw

        # Default: no OCR needed
        ocr_decision = "n/a"

        if p_type == "digital":
            # Text is good — store it, no OCR
            digital_pages.append(i)
            digital_text[i] = page_texts[i]

        elif p_type in ("scanned", "partial"):
            # --- Doc-type overrides ---
            if doc_type == "bank_statement":
                # Bank statements are digital CSVs; skip OCR entirely
                ocr_decision = "ocr_skip"
                ocr_skip.append(i)
            elif doc_type == "gst_filing":
                # GST filings: every scanned page is important
                ocr_decision = "ocr_priority"
                ocr_priority.append(i)
            else:
                # Standard keyword + neighbor heuristic
                if has_kw or neighbor_kw:
                    ocr_decision = "ocr_priority"
                    ocr_priority.append(i)
                else:
                    ocr_decision = "ocr_skip"
                    ocr_skip.append(i)

        # BLANK pages get NOT_APPLICABLE — nothing to do

        pages.append(
            PageClassification(
                page_number=i,
                page_type=p_type,
                ocr_decision=ocr_decision,
                text_char_count=len(page_texts[i]),
                has_financial_keywords=has_kw,
                neighbor_has_keywords=neighbor_kw,
            )
        )

    result = PageClassificationResult(
        total_pages=total,
        digital_pages=digital_pages,
        ocr_priority_pages=ocr_priority,
        ocr_skip_pages=ocr_skip,
        estimated_ocr_pages=len(ocr_priority),
        digital_text=digital_text,
        pages=pages,
    )

    logger.info(
        f"Classification complete: {total} pages — "
        f"{len(digital_pages)} digital, "
        f"{len(ocr_priority)} OCR priority, "
        f"{len(ocr_skip)} OCR skip, "
        f"{total - len(digital_pages) - len(ocr_priority) - len(ocr_skip)} blank"
    )

    return result
