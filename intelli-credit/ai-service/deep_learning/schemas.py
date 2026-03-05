"""
Pydantic v2 schemas for the Deep Learning / Document Intelligence module.

All models used across page_classifier, ocr_engine, info_extractor, and main.py
are defined here as the single source of truth.

Models:
  1. PageClassification / PageClassificationResult  — page_classifier.py
  2. OCRPageResult                                   — ocr_engine.py
  3. MergedPage / MergedDocument                     — ocr_engine.merge_document_text()
  4. FinancialExtraction (+ sub-models)              — info_extractor.extract_financial_ratios()
  5. EntityExtraction (+ sub-models)                 — info_extractor.extract_entities()
  6. DocumentProcessingResult                        — final output → ocr_output.json
  7. ProcessDocumentRequest / ProcessDocumentResponse — API layer
"""

from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field


# =============================================================================
# 1. PAGE CLASSIFIER
# =============================================================================

class PageClassification(BaseModel):
    """Per-page classification detail produced by classify_pages()."""

    model_config = {"json_schema_extra": {"title": "PageClassification"}}

    page_number: int = Field(
        ..., description="0-indexed page number within the PDF"
    )
    page_type: Literal["digital", "scanned", "partial", "blank"] = Field(
        ...,
        description=(
            "Page classification: 'digital' (>200 chars, born-digital), "
            "'scanned' (<50 chars, needs OCR), 'partial' (50-200 chars, "
            "lower-priority OCR), 'blank' (0 chars, skip)"
        ),
    )
    ocr_decision: Literal["ocr_priority", "ocr_skip", "n/a"] = Field(
        default="n/a",
        description=(
            "'ocr_priority' = send to DeepSeek-OCR, "
            "'ocr_skip' = scanned but not financially relevant, "
            "'n/a' = digital or blank page"
        ),
    )
    text_char_count: int = Field(
        ..., description="Number of characters extracted by PyMuPDF from this page"
    )
    has_financial_keywords: bool = Field(
        default=False,
        description="True if financial keywords found on this page (exact or fuzzy match)",
    )
    neighbor_has_keywords: bool = Field(
        default=False,
        description="True if the immediately preceding or following page has financial keywords",
    )


class PageClassificationResult(BaseModel):
    """
    Aggregate classification result for an entire PDF.
    Returned by classify_pages() and consumed by the OCR + merge pipeline.
    """

    model_config = {"json_schema_extra": {"title": "PageClassificationResult"}}

    total_pages: int = Field(
        ..., description="Total number of pages in the PDF"
    )
    digital_pages: List[int] = Field(
        default_factory=list,
        description="0-indexed page numbers classified as DIGITAL (text extracted by PyMuPDF)",
    )
    ocr_priority_pages: List[int] = Field(
        default_factory=list,
        description="0-indexed page numbers selected for DeepSeek-OCR (scanned + financially relevant)",
    )
    ocr_skip_pages: List[int] = Field(
        default_factory=list,
        description="0-indexed scanned page numbers NOT sent to OCR (not financially relevant)",
    )
    estimated_ocr_pages: int = Field(
        default=0,
        description="Count of ocr_priority_pages — the number of pages that will be OCR'd",
    )
    digital_text: Dict[int, str] = Field(
        default_factory=dict,
        description="Pre-extracted text for DIGITAL pages: {page_num: text}. Bypasses OCR entirely.",
    )
    encrypted: bool = Field(
        default=False,
        description="True if the PDF is encrypted and could not be opened without a password",
    )
    encryption_error: Optional[str] = Field(
        default=None,
        description="Error message if encryption prevented processing; null if PDF is not encrypted",
    )
    pages: List[PageClassification] = Field(
        default_factory=list,
        description="Per-page classification details for every page in the PDF",
    )


# =============================================================================
# 2. OCR ENGINE
# =============================================================================

class OCRPageResult(BaseModel):
    """
    OCR output for a single page from local DeepSeek-VL2-tiny inference.
    Returned by ocr_single_page() and aggregated by ocr_document().
    """

    model_config = {"json_schema_extra": {"title": "OCRPageResult"}}

    page_number: int = Field(
        ..., description="0-indexed page number that was OCR'd"
    )
    raw_text: str = Field(
        default="",
        description="Extracted text and Markdown tables from the page image",
    )
    has_table: bool = Field(
        default=False,
        description="True if pipe '|' characters detected, indicating a Markdown table",
    )
    confidence: Literal["HIGH", "LOW", "FAILED"] = Field(
        default="HIGH",
        description="HIGH if raw_text > 100 chars, LOW if sparse output, FAILED on inference error",
    )


# =============================================================================
# 3. MERGED DOCUMENT (post-OCR)
# =============================================================================

class MergedPage(BaseModel):
    """Single page in the merged document produced by merge_document_text()."""

    model_config = {"json_schema_extra": {"title": "MergedPage"}}

    page_num: int = Field(
        ..., description="0-indexed page number"
    )
    source: Literal["DIGITAL", "OCR", "SKIPPED"] = Field(
        ...,
        description=(
            "'DIGITAL' = text from PyMuPDF (born-digital), "
            "'OCR' = text from DeepSeek-VL2, "
            "'SKIPPED' = page was blank or OCR-skipped"
        ),
    )
    text: str = Field(
        default="",
        description="Extracted text content for this page (empty if SKIPPED)",
    )


class MergedDocument(BaseModel):
    """
    Complete merged document text in page order.
    Produced by merge_document_text(), consumed by info_extractor.
    Also writes extracted.txt to the shared volume (V11 fix).
    """

    model_config = {"json_schema_extra": {"title": "MergedDocument"}}

    full_text: str = Field(
        ..., description="All page text concatenated in order with '--- PAGE N ---' separators"
    )
    pages: List[MergedPage] = Field(
        default_factory=list,
        description="Per-page breakdown showing source and text for each page",
    )
    total_pages: int = Field(
        default=0, description="Total number of pages in the original PDF"
    )
    digital_page_count: int = Field(
        default=0, description="Number of pages where text was extracted by PyMuPDF"
    )
    ocr_page_count: int = Field(
        default=0, description="Number of pages processed by DeepSeek-VL2 OCR"
    )
    skipped_page_count: int = Field(
        default=0, description="Number of pages skipped (blank or not financially relevant)"
    )
    has_ocr_failures: bool = Field(
        default=False,
        description="True if any OCR page returned confidence='FAILED'",
    )


# =============================================================================
# 4. FINANCIAL EXTRACTION (Claude)
# =============================================================================

class FYValue(BaseModel):
    """A financial figure with fiscal year breakdown (V4 fix: null if uncertain)."""

    model_config = {"json_schema_extra": {"title": "FYValue"}}

    fy_current: Optional[float] = Field(
        default=None, description="Value for the most recent fiscal year (in Crores)"
    )
    fy_previous: Optional[float] = Field(
        default=None, description="Value for the previous fiscal year (in Crores)"
    )
    fy_two_years_ago: Optional[float] = Field(
        default=None, description="Value for two fiscal years ago (in Crores)"
    )
    unit_in_document: Optional[str] = Field(
        default=None,
        description="Original unit as stated in the document: 'Lakhs', 'Crores', 'Rs.', etc.",
    )


class DebtSnapshot(BaseModel):
    """Point-in-time debt or net worth figure."""

    model_config = {"json_schema_extra": {"title": "DebtSnapshot"}}

    value: Optional[float] = Field(
        default=None, description="Amount in Crores (normalized from original unit)"
    )
    as_of_date: Optional[str] = Field(
        default=None, description="Date the figure was reported, e.g. '31-Mar-2024'"
    )


class FinancialExtraction(BaseModel):
    """
    Structured financial data extracted by Claude from document text.
    V4 fix: every field is nullable — Claude returns null rather than guess
    when year labeling is uncertain or the figure is not explicitly stated.
    """

    model_config = {"json_schema_extra": {"title": "FinancialExtraction"}}

    doc_type: str = Field(
        ..., description="Document type that was processed"
    )
    extraction_model: str = Field(
        default="claude-haiku-4-5-20251001",
        description="Claude model used for extraction",
    )
    confidence: Literal["HIGH", "LOW"] = Field(
        default="HIGH",
        description="HIGH if fewer than 4 critical fields are null; LOW if 4+ critical nulls",
    )

    # --- Annual Report fields ---
    revenue: Optional[FYValue] = Field(
        default=None, description="Revenue from operations across fiscal years"
    )
    ebitda: Optional[FYValue] = Field(
        default=None, description="EBITDA (Earnings Before Interest, Taxes, Depreciation & Amortization)"
    )
    pat: Optional[FYValue] = Field(
        default=None, description="PAT (Profit After Tax) across fiscal years"
    )
    total_debt: Optional[DebtSnapshot] = Field(
        default=None, description="Total outstanding debt as of a specific date"
    )
    net_worth: Optional[DebtSnapshot] = Field(
        default=None, description="Net worth (shareholders' equity) as of a specific date"
    )
    current_assets: Optional[float] = Field(
        default=None, description="Total current assets in Crores"
    )
    current_liabilities: Optional[float] = Field(
        default=None, description="Total current liabilities in Crores"
    )
    ebit: Optional[float] = Field(
        default=None, description="EBIT (Earnings Before Interest & Taxes) in Crores"
    )
    interest_expense: Optional[float] = Field(
        default=None, description="Total interest/finance costs in Crores"
    )
    operating_cash_flow: Optional[float] = Field(
        default=None, description="Cash flow from operating activities in Crores"
    )
    debt_service: Optional[float] = Field(
        default=None, description="Total debt service (principal + interest) in Crores"
    )
    auditor_qualification: Optional[str] = Field(
        default=None, description="Auditor qualification or emphasis of matter, if any"
    )
    auditor_name: Optional[str] = Field(
        default=None, description="Name of the statutory auditor / audit firm"
    )
    fiscal_year_end: Optional[str] = Field(
        default=None, description="Fiscal year end date, e.g. '31-Mar-2024'"
    )
    extraction_notes: Optional[str] = Field(
        default=None,
        description="Any ambiguity, merged cells, or confidence issues observed by Claude",
    )

    # --- GST Filing fields ---
    gst_turnover_declared: Optional[float] = Field(
        default=None, description="GST turnover declared in Crores"
    )
    itc_claimed_3b: Optional[float] = Field(
        default=None, description="ITC claimed in GSTR-3B in Crores"
    )
    period_covered: Optional[str] = Field(
        default=None, description="Period covered by the GST filing, e.g. 'Apr 2023 - Mar 2024'"
    )
    gstin: Optional[str] = Field(
        default=None, description="GSTIN (GST Identification Number)"
    )

    # --- Rating Report fields ---
    rating_assigned: Optional[str] = Field(
        default=None, description="Credit rating assigned, e.g. 'CRISIL BBB+'"
    )
    rating_outlook: Optional[str] = Field(
        default=None, description="Rating outlook: 'Stable', 'Positive', 'Negative', 'Watch'"
    )
    rating_date: Optional[str] = Field(
        default=None, description="Date the rating was assigned"
    )
    rating_agency: Optional[str] = Field(
        default=None, description="Rating agency name: CRISIL, ICRA, CARE, India Ratings, etc."
    )
    key_rationale_summary: Optional[str] = Field(
        default=None, description="Key rating rationale in max 3 sentences"
    )
    previous_rating: Optional[str] = Field(
        default=None, description="Previous credit rating, if mentioned"
    )


# =============================================================================
# 5. ENTITY EXTRACTION (Claude NER)
# =============================================================================

class PromoterEntity(BaseModel):
    """A promoter or director entity extracted from the document."""

    model_config = {"json_schema_extra": {"title": "PromoterEntity"}}

    name: str = Field(..., description="Full name with initials as written in the document")
    designation: Optional[str] = Field(
        default=None, description="Designation: 'Managing Director', 'Chairman', 'Promoter', etc."
    )
    din: Optional[str] = Field(
        default=None, description="Director Identification Number (DIN), if stated"
    )


class RelatedPartyEntity(BaseModel):
    """A related party with transaction details."""

    model_config = {"json_schema_extra": {"title": "RelatedPartyEntity"}}

    name: str = Field(..., description="Full legal name of the related party")
    relationship: Optional[str] = Field(
        default=None, description="Relationship type: 'Subsidiary', 'Associate', 'KMP', etc."
    )
    transaction_amount_crore: Optional[float] = Field(
        default=None, description="Transaction amount with this party in Crores"
    )


class SubsidiaryEntity(BaseModel):
    """A subsidiary company."""

    model_config = {"json_schema_extra": {"title": "SubsidiaryEntity"}}

    name: str = Field(..., description="Full legal name including suffix (Pvt Ltd, LLP, etc.)")
    cin: Optional[str] = Field(
        default=None, description="Corporate Identification Number of the subsidiary"
    )


class LenderEntity(BaseModel):
    """An existing lender or bank facility."""

    model_config = {"json_schema_extra": {"title": "LenderEntity"}}

    bank_name: str = Field(..., description="Name of the lending bank or financial institution")
    facility_type: Optional[str] = Field(
        default=None, description="Type of facility: 'Term Loan', 'CC/OD', 'LC', 'BG', etc."
    )
    amount_crore: Optional[float] = Field(
        default=None, description="Sanctioned or outstanding amount in Crores"
    )


class GuarantorEntity(BaseModel):
    """A guarantor for the borrower."""

    model_config = {"json_schema_extra": {"title": "GuarantorEntity"}}

    name: str = Field(..., description="Full name of the guarantor")
    relationship_to_borrower: Optional[str] = Field(
        default=None, description="Relationship: 'Promoter', 'Director', 'Group Company', etc."
    )


class AuditorEntity(BaseModel):
    """Auditor information."""

    model_config = {"json_schema_extra": {"title": "AuditorEntity"}}

    name: Optional[str] = Field(
        default=None, description="Name of the signing partner"
    )
    firm: Optional[str] = Field(
        default=None, description="Audit firm name, e.g. 'Deloitte Haskins & Sells LLP'"
    )


class EntityExtraction(BaseModel):
    """
    Named entities extracted by Claude for the Entity Graph module.
    All entities are exact legal names as stated in the document — no paraphrasing.
    """

    model_config = {"json_schema_extra": {"title": "EntityExtraction"}}

    source_doc_type: str = Field(
        ..., description="Document type the entities were extracted from"
    )
    entity_count: int = Field(
        default=0, description="Total number of entities found across all categories"
    )
    extraction_model: str = Field(
        default="claude-haiku-4-5-20251001",
        description="Claude model used for entity extraction",
    )

    company_name: Optional[str] = Field(
        default=None, description="Full legal name of the company, including suffix"
    )
    cin: Optional[str] = Field(
        default=None, description="Corporate Identification Number (CIN) of the company"
    )
    promoters: List[PromoterEntity] = Field(
        default_factory=list, description="List of promoters and key directors"
    )
    related_parties: List[RelatedPartyEntity] = Field(
        default_factory=list, description="Related party entities with transaction details"
    )
    subsidiaries: List[SubsidiaryEntity] = Field(
        default_factory=list, description="Subsidiary companies"
    )
    existing_lenders: List[LenderEntity] = Field(
        default_factory=list, description="Existing bank facilities and lenders"
    )
    collateral_descriptions: List[str] = Field(
        default_factory=list, description="Descriptions of collateral/security offered"
    )
    guarantors: List[GuarantorEntity] = Field(
        default_factory=list, description="Personal or corporate guarantors"
    )
    auditor: Optional[AuditorEntity] = Field(
        default=None, description="Statutory auditor details"
    )


# =============================================================================
# 6. COMBINED EXTRACTION RESULT
# =============================================================================

class ExtractionResult(BaseModel):
    """Combined financial + entity extraction output from Claude."""

    model_config = {"json_schema_extra": {"title": "ExtractionResult"}}

    doc_type: str = Field(
        ..., description="Document type that was processed"
    )
    financial_extraction: Optional[FinancialExtraction] = Field(
        default=None, description="Structured financial data extracted by Claude"
    )
    entity_extraction: Optional[EntityExtraction] = Field(
        default=None, description="Named entities extracted by Claude for the Entity Graph"
    )


# =============================================================================
# 7. FINAL OUTPUT — Written to ocr_output.json
# =============================================================================

class DocumentProcessingResult(BaseModel):
    """
    Final output written to /tmp/intelli-credit/{job_id}/ocr_output.json.
    This is the complete result of the document processing pipeline.
    The web developer reads this JSON to display results in the frontend.
    """

    model_config = {"json_schema_extra": {"title": "DocumentProcessingResult"}}

    job_id: str = Field(
        ..., description="Unique job identifier from the orchestrator"
    )
    doc_type: Literal[
        "annual_report", "bank_statement", "gst_filing", "rating_report", "legal_notice"
    ] = Field(
        ..., description="Type of financial document that was processed"
    )
    status: Literal["success", "partial", "failed"] = Field(
        ...,
        description=(
            "'success' = all pipeline stages completed, "
            "'partial' = completed with some OCR failures or low-confidence extractions, "
            "'failed' = critical error prevented processing"
        ),
    )
    file_path_extracted_text: str = Field(
        ...,
        description="Path to the merged extracted text file: /tmp/intelli-credit/{job_id}/extracted.txt",
    )
    page_classification: PageClassificationResult = Field(
        ..., description="Full page classification result from the V6 smart targeting pipeline"
    )
    financial_extraction: Optional[FinancialExtraction] = Field(
        default=None, description="Structured financial data extracted by Claude (null on failure)"
    )
    entity_extraction: Optional[EntityExtraction] = Field(
        default=None, description="Named entities extracted by Claude (null on failure)"
    )
    processing_time_seconds: float = Field(
        ..., description="Total wall-clock time for the entire pipeline in seconds"
    )
    errors: List[str] = Field(
        default_factory=list,
        description="List of non-fatal errors encountered during processing (empty on clean run)",
    )


# =============================================================================
# 8. API REQUEST / RESPONSE
# =============================================================================

class ProcessDocumentRequest(BaseModel):
    """
    POST /api/v1/process-document request body.
    Sent by the orchestrator to kick off document processing.
    """

    model_config = {"json_schema_extra": {"title": "ProcessDocumentRequest"}}

    job_id: str = Field(
        ..., description="Unique job identifier assigned by the orchestrator"
    )
    file_path: str = Field(
        ...,
        description="Absolute path to the PDF file inside the shared Docker volume, e.g. /tmp/intelli-credit/{job_id}/document.pdf",
    )
    doc_type: Literal[
        "annual_report", "bank_statement", "gst_filing", "rating_report", "legal_notice"
    ] = Field(
        ...,
        description="Type of financial document to process",
    )


class ProcessDocumentResponse(BaseModel):
    """
    Immediate response from POST /api/v1/process-document.
    Processing continues in the background after this response is sent.
    """

    model_config = {"json_schema_extra": {"title": "ProcessDocumentResponse"}}

    status: Literal["processing"] = Field(
        default="processing",
        description="Always 'processing' — the actual result is polled via GET /api/v1/status/{job_id}",
    )
    job_id: str = Field(
        ..., description="Echo of the job_id from the request"
    )
    message: str = Field(
        default="Document processing started. Poll /api/v1/status/{job_id} for results.",
        description="Human-readable status message for the caller",
    )


class JobStatusResponse(BaseModel):
    """
    GET /api/v1/status/{job_id} response.
    Returns the full processing result once complete, or a processing status if still running.
    """

    model_config = {"json_schema_extra": {"title": "JobStatusResponse"}}

    job_id: str = Field(
        ..., description="The job identifier being queried"
    )
    status: Literal["processing", "success", "partial", "failed"] = Field(
        ..., description="Current job status"
    )
    result: Optional[DocumentProcessingResult] = Field(
        default=None,
        description="Full processing result (only present when status != 'processing')",
    )
    error: Optional[str] = Field(
        default=None, description="Error message if status is 'failed'"
    )
