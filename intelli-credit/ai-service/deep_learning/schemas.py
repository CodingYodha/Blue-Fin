"""
Pydantic schemas for the Deep Learning / Document Intelligence module.
Covers request/response models for OCR, page classification, and extraction.
"""

from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


# =============================================================================
# ENUMS
# =============================================================================

class DocType(str, Enum):
    """Supported document types for processing."""
    ANNUAL_REPORT = "annual_report"
    BANK_STATEMENT = "bank_statement"
    GST_FILING = "gst_filing"
    RATING_REPORT = "rating_report"
    LEGAL_NOTICE = "legal_notice"


class PageType(str, Enum):
    """Classification result for individual PDF pages."""
    DIGITAL = "digital"          # Born-digital, >200 chars — PyMuPDF handles directly
    SCANNED = "scanned"          # <50 chars — full OCR candidate
    PARTIAL = "partial"          # 50-200 chars — lower-priority OCR candidate
    BLANK = "blank"              # 0 chars — skip entirely


class OCRDecision(str, Enum):
    """Whether a scanned/partial page should be sent to DeepSeek-OCR."""
    OCR_PRIORITY = "ocr_priority"    # Financially relevant → send to OCR
    OCR_SKIP = "ocr_skip"           # Scanned but not financially relevant
    NOT_APPLICABLE = "n/a"          # Digital or blank — no OCR needed


class ProcessingStatus(str, Enum):
    """Job lifecycle states."""
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


# =============================================================================
# REQUEST / RESPONSE — API Layer
# =============================================================================

class ProcessDocumentRequest(BaseModel):
    """POST /api/v1/process-document body."""
    job_id: str = Field(..., description="Unique job identifier from the orchestrator")
    file_path: str = Field(..., description="Path to PDF inside shared Docker volume")
    doc_type: DocType = Field(..., description="Type of financial document")


class ProcessDocumentResponse(BaseModel):
    """Immediate acknowledgement returned to caller."""
    status: str = "processing"
    job_id: str


class JobStatusResponse(BaseModel):
    """GET /api/v1/status/{job_id} response."""
    job_id: str
    status: ProcessingStatus
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


# =============================================================================
# INTERNAL — Page Classifier
# =============================================================================

class PageClassification(BaseModel):
    """Classification detail for a single PDF page."""
    page_number: int = Field(..., description="0-indexed page number")
    page_type: PageType
    ocr_decision: OCRDecision = OCRDecision.NOT_APPLICABLE
    text_char_count: int = Field(
        ..., description="Number of characters extracted by PyMuPDF"
    )
    has_financial_keywords: bool = Field(
        default=False,
        description="True if financial keywords found on this page (exact or fuzzy)"
    )
    neighbor_has_keywords: bool = Field(
        default=False,
        description="True if the page before or after has financial keywords"
    )


class PageClassificationResult(BaseModel):
    """
    Aggregate classification for an entire PDF.
    Returned by classify_pages() to downstream pipeline stages.
    """
    total_pages: int
    digital_pages: List[int] = Field(
        default_factory=list,
        description="0-indexed page numbers classified as DIGITAL"
    )
    ocr_priority_pages: List[int] = Field(
        default_factory=list,
        description="0-indexed page numbers to send to DeepSeek-OCR"
    )
    ocr_skip_pages: List[int] = Field(
        default_factory=list,
        description="0-indexed scanned pages not financially relevant (skipped)"
    )
    estimated_ocr_pages: int = Field(
        default=0,
        description="Count of ocr_priority_pages"
    )
    digital_text: Dict[int, str] = Field(
        default_factory=dict,
        description="Extracted text for DIGITAL pages {page_num: text}, bypasses OCR"
    )
    encrypted: bool = Field(
        default=False,
        description="True if the PDF is encrypted and could not be opened"
    )
    encryption_error: Optional[str] = Field(
        default=None,
        description="Error message if encryption prevented processing"
    )
    pages: List[PageClassification] = Field(default_factory=list)


# =============================================================================
# INTERNAL — OCR Engine (Local DeepSeek-VL2)
# =============================================================================

class OCRPageResult(BaseModel):
    """OCR output for a single page from local DeepSeek-VL2 inference."""
    page_number: int = Field(..., description="0-indexed page number")
    raw_text: str = Field(
        default="", description="Extracted text/tables in Markdown format"
    )
    has_table: bool = Field(
        default=False, description="True if pipe characters detected (Markdown table)"
    )
    confidence: str = Field(
        default="HIGH",
        description="HIGH if raw_text > 100 chars, LOW if sparse, FAILED on error"
    )


# OCR document result is a dict: {page_num: OCRPageResult}
# No wrapper class needed — ocr_document() returns Dict[int, OCRPageResult]


# =============================================================================
# INTERNAL — Merged Document (post-OCR)
# =============================================================================

class MergedPage(BaseModel):
    """Single page in the merged document."""
    page_number: int = Field(..., description="0-indexed page number")
    source: str = Field(
        ..., description="'DIGITAL' (PyMuPDF), 'OCR' (DeepSeek), or 'SKIPPED'"
    )
    text: str = Field(default="", description="Extracted text for this page")


class MergedDocument(BaseModel):
    """
    Complete merged document text in page order.
    Produced by merge_document_text(), consumed by info_extractor.
    """
    full_text: str = Field(
        ..., description="All pages concatenated with page separators"
    )
    pages: List[MergedPage] = Field(default_factory=list)
    total_pages: int = 0
    digital_page_count: int = 0
    ocr_page_count: int = 0
    skipped_page_count: int = 0
    has_ocr_failures: bool = Field(
        default=False,
        description="True if any OCR page returned confidence='FAILED'"
    )


# =============================================================================
# INTERNAL — Structured Info Extraction (Claude)
# =============================================================================

class ExtractedFinancials(BaseModel):
    """Structured financial data extracted by Claude from document text."""
    revenue_fy: Optional[Dict[str, Optional[float]]] = Field(
        default=None,
        description="Revenue by fiscal year, e.g. {'FY2022': 48.2, 'FY2023': 44.1, 'FY2024': 41.0}"
    )
    ebitda_margin: Optional[float] = None
    net_profit_margin: Optional[float] = None
    total_debt_crore: Optional[float] = None
    net_worth_crore: Optional[float] = None
    dscr: Optional[float] = None
    debt_to_equity: Optional[float] = None
    interest_coverage_ratio: Optional[float] = None
    current_ratio: Optional[float] = None


class ExtractedEntities(BaseModel):
    """Named entities extracted from the document."""
    company_name: Optional[str] = None
    cin: Optional[str] = None
    promoter_names: List[str] = Field(default_factory=list)
    directors: List[str] = Field(default_factory=list)
    auditor: Optional[str] = None
    related_parties: List[str] = Field(default_factory=list)


class ExtractedRiskSignals(BaseModel):
    """Risk-related signals extracted from the document."""
    auditor_qualifications: List[str] = Field(default_factory=list)
    contingent_liabilities: List[str] = Field(default_factory=list)
    covenant_breaches: List[str] = Field(default_factory=list)
    litigation_mentions: List[str] = Field(default_factory=list)
    going_concern_flag: bool = False


class ExtractionResult(BaseModel):
    """Complete structured extraction output for a document."""
    doc_type: DocType
    financials: Optional[ExtractedFinancials] = None
    entities: Optional[ExtractedEntities] = None
    risk_signals: Optional[ExtractedRiskSignals] = None
    raw_text_pages: int = Field(
        default=0, description="Total pages whose text was used for extraction"
    )
    confidence: str = Field(
        default="HIGH",
        description="HIGH if Go-service cross-verified; LOW if manual check needed"
    )


# =============================================================================
# FINAL OUTPUT — Written to ocr_output.json
# =============================================================================

class DocumentProcessingOutput(BaseModel):
    """Final JSON written to /tmp/intelli-credit/{job_id}/ocr_output.json."""
    job_id: str
    status: ProcessingStatus
    doc_type: DocType
    page_classification: Optional[PageClassificationResult] = None
    ocr_results: Optional[Dict[str, OCRPageResult]] = Field(
        default=None,
        description="OCR results keyed by page number (as string for JSON compat)"
    )
    extraction: Optional[ExtractionResult] = None
    error: Optional[str] = None
