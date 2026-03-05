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

# --- Financial Extraction sub-models ---

class FYValue(BaseModel):
    """A financial figure with fiscal year breakdown (V4 fix: null if uncertain)."""
    fy_current: Optional[float] = None
    fy_previous: Optional[float] = None
    fy_two_years_ago: Optional[float] = None
    unit_in_document: Optional[str] = Field(
        default=None, description="Original unit in document: 'Lakhs', 'Crores', 'Rs.'"
    )


class DebtSnapshot(BaseModel):
    """Point-in-time debt or net worth figure."""
    value: Optional[float] = Field(default=None, description="Value in Crores")
    as_of_date: Optional[str] = None


class FinancialExtraction(BaseModel):
    """
    Structured financial data extracted by Claude.
    V4 fix: every field is nullable — Claude returns null rather than guess.
    """
    doc_type: str
    extraction_model: str = "claude-haiku-4-5-20251001"
    confidence: str = Field(
        default="HIGH",
        description="HIGH if <4 critical nulls, LOW if >=4 critical fields are null"
    )

    # Annual Report fields
    revenue: Optional[FYValue] = None
    ebitda: Optional[FYValue] = None
    pat: Optional[FYValue] = None
    total_debt: Optional[DebtSnapshot] = None
    net_worth: Optional[DebtSnapshot] = None
    current_assets: Optional[float] = None
    current_liabilities: Optional[float] = None
    ebit: Optional[float] = None
    interest_expense: Optional[float] = None
    operating_cash_flow: Optional[float] = None
    debt_service: Optional[float] = None
    auditor_qualification: Optional[str] = None
    auditor_name: Optional[str] = None
    fiscal_year_end: Optional[str] = None
    extraction_notes: Optional[str] = None

    # GST Filing fields
    gst_turnover_declared: Optional[float] = None
    itc_claimed_3b: Optional[float] = None
    period_covered: Optional[str] = None
    gstin: Optional[str] = None

    # Rating Report fields
    rating_assigned: Optional[str] = None
    rating_outlook: Optional[str] = None
    rating_date: Optional[str] = None
    rating_agency: Optional[str] = None
    key_rationale_summary: Optional[str] = None
    previous_rating: Optional[str] = None


# --- Entity Extraction sub-models ---

class PromoterEntity(BaseModel):
    """A promoter/director entity."""
    name: str
    designation: Optional[str] = None
    din: Optional[str] = None


class RelatedPartyEntity(BaseModel):
    """A related party with transaction details."""
    name: str
    relationship: Optional[str] = None
    transaction_amount_crore: Optional[float] = None


class SubsidiaryEntity(BaseModel):
    """A subsidiary company."""
    name: str
    cin: Optional[str] = None


class LenderEntity(BaseModel):
    """An existing lender/bank facility."""
    bank_name: str
    facility_type: Optional[str] = None
    amount_crore: Optional[float] = None


class GuarantorEntity(BaseModel):
    """A guarantor for the borrower."""
    name: str
    relationship_to_borrower: Optional[str] = None


class AuditorEntity(BaseModel):
    """Auditor information."""
    name: Optional[str] = None
    firm: Optional[str] = None


class EntityExtraction(BaseModel):
    """
    Named entities extracted by Claude for the Entity Graph module.
    All entities are exact legal names as stated in the document.
    """
    source_doc_type: str
    entity_count: int = 0
    extraction_model: str = "claude-haiku-4-5-20251001"

    company_name: Optional[str] = None
    cin: Optional[str] = None
    promoters: List[PromoterEntity] = Field(default_factory=list)
    related_parties: List[RelatedPartyEntity] = Field(default_factory=list)
    subsidiaries: List[SubsidiaryEntity] = Field(default_factory=list)
    existing_lenders: List[LenderEntity] = Field(default_factory=list)
    collateral_descriptions: List[str] = Field(default_factory=list)
    guarantors: List[GuarantorEntity] = Field(default_factory=list)
    auditor: Optional[AuditorEntity] = None


# --- Combined extraction result ---

class ExtractionResult(BaseModel):
    """Combined financial + entity extraction output."""
    doc_type: str
    financial_extraction: Optional[FinancialExtraction] = None
    entity_extraction: Optional[EntityExtraction] = None


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
