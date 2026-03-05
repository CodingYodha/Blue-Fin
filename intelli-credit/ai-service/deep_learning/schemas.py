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
    TEXT_RICH = "text_rich"       # Born-digital, PyMuPDF can handle
    SCANNED = "scanned"          # Needs OCR (DeepSeek)
    BLANK = "blank"              # Skip entirely


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
    """Result of classifying a single PDF page."""
    page_number: int
    page_type: PageType
    text_char_count: int = Field(
        ..., description="Number of characters extracted by PyMuPDF"
    )
    has_financial_keywords: bool = Field(
        default=False,
        description="True if page contains keywords like 'Balance Sheet', 'GSTR', etc."
    )
    send_to_ocr: bool = Field(
        default=False,
        description="True if this page should be sent to DeepSeek-OCR"
    )


class PageClassificationResult(BaseModel):
    """Aggregate classification for an entire PDF."""
    total_pages: int
    text_rich_pages: int
    scanned_pages: int
    blank_pages: int
    ocr_target_pages: List[int] = Field(
        default_factory=list,
        description="Page numbers selected for OCR (scanned + financial keyword)"
    )
    pages: List[PageClassification]


# =============================================================================
# INTERNAL — OCR Engine
# =============================================================================

class OCRPageResult(BaseModel):
    """OCR output for a single page."""
    page_number: int
    markdown_text: str = Field(
        ..., description="Reconstructed text/table in Markdown format"
    )
    confidence: float = Field(
        default=0.0, ge=0.0, le=1.0,
        description="OCR confidence score"
    )
    tables_detected: int = Field(
        default=0, description="Number of tables found on this page"
    )


class OCRResult(BaseModel):
    """Aggregate OCR output for all processed pages."""
    pages_processed: int
    results: List[OCRPageResult]


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
    ocr_result: Optional[OCRResult] = None
    extraction: Optional[ExtractionResult] = None
    error: Optional[str] = None
