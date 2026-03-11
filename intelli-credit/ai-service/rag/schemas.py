"""
RAG Module Schemas — Pydantic v2 models for the RAG pipeline.

=============================================================================
Centralized schema definitions for all RAG sub-modules.
Keeps data contracts in one place — change here, propagates everywhere.

Models:
  1.  ChunkInput              — input to the embedder
  2.  ChunkEmbedding          — output from the embedder (text + vector + metadata)
  3.  GoChunk                 — format written by Go service in chunks.json
  4.  IngestRequest           — POST /rag/ingest request body
  5.  IngestResult            — result of ingesting one doc_type
  6.  RetrievedChunk          — a chunk returned by Qdrant search
  7.  ExtractedValue          — a financial figure with provenance
  8.  FinancialSummaryExtraction — Claude-extracted financial summary
  9.  QualitativeExtraction   — Claude-extracted qualitative signals
  10. CovenantExtraction      — Claude-extracted covenant + collateral
  11. RatingExtraction        — Claude-extracted rating intelligence
  12. RAGExtractionResult     — combined output from all extraction functions
  13. QueryRequest            — POST /rag/query request body
  14. QueryResponse           — response from semantic search
=============================================================================
"""

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from model_config import CLAUDE_RAG_EXTRACTION_MODEL


# =============================================================================
# 1. EMBEDDER INPUT / OUTPUT
# =============================================================================

class ChunkInput(BaseModel):
    """Input to the batch embedder: text + metadata."""

    model_config = ConfigDict(
        json_schema_extra={"title": "ChunkInput"},
    )

    chunk_text: str = Field(..., description="Text content of the chunk")
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Metadata to carry alongside the embedding (job_id, doc_type, etc.)",
    )


class ChunkEmbedding(BaseModel):
    """Output from the batch embedder: text + vector + metadata."""

    model_config = ConfigDict(
        json_schema_extra={"title": "ChunkEmbedding"},
    )

    chunk_text: str = Field(..., description="Text content of the chunk")
    vector: List[float] = Field(..., description="768-dim embedding vector from Jina")
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Original metadata passed through from ChunkInput",
    )


# =============================================================================
# 2. GO SERVICE CHUNK FORMAT
# =============================================================================

class GoChunk(BaseModel):
    """
    Schema matching the chunks.json format produced by the Go service.

    Go owns chunking — ai-service reads this file directly, no re-chunking.
    """

    model_config = ConfigDict(
        json_schema_extra={"title": "GoChunk"},
    )

    chunk_text: str = Field(..., description="Text content of the chunk")
    page_num: int = Field(default=0, description="Page number in source document")
    section_name: str = Field(default="", description="Section name from the chunker")
    chunk_index: int = Field(default=0, description="Position of this chunk within its document")
    doc_type: str = Field(
        ...,
        description="Document type: 'annual_report', 'rating_report', 'legal_notice', 'gst_filing'",
    )
    source_file: str = Field(default="", description="Original filename")


# =============================================================================
# 3. INGEST MODELS
# =============================================================================

class IngestRequest(BaseModel):
    """POST /api/v1/rag/ingest request body."""

    model_config = ConfigDict(
        json_schema_extra={"title": "IngestRequest"},
    )

    job_id: str = Field(..., description="Loan application job ID")
    company_name: str = Field(..., description="Borrower company name")
    doc_types: List[
        Literal["annual_report", "rating_report", "legal_notice", "gst_filing", "gst_3b", "gst_2a", "gst_1"]
    ] = Field(
        ...,
        description="Document types to ingest (only include types actually uploaded)",
    )


class IngestResult(BaseModel):
    """Result of ingesting chunks for a single doc_type."""

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={"title": "IngestResult"},
    )

    job_id: str = Field(..., description="Job ID")
    doc_type: str = Field(..., description="Document type processed")
    chunks_read: int = Field(default=0, description="Chunks read from chunks.json")
    chunks_embedded: int = Field(default=0, description="Chunks successfully embedded via Jina")
    chunks_stored: int = Field(default=0, description="Chunks stored in Qdrant")
    high_priority_count: int = Field(default=0, description="Chunks with HIGH embed priority")
    medium_priority_count: int = Field(default=0, description="Chunks with MEDIUM embed priority")
    low_priority_count: int = Field(default=0, description="Chunks with LOW embed priority")
    status: Literal["success", "skipped", "partial", "failed"] = Field(
        default="success",
        description="Outcome of the ingest operation",
    )
    error: Optional[str] = Field(
        default=None, description="Error message if status is 'failed' or 'skipped'"
    )


# =============================================================================
# 4. RETRIEVER MODELS
# =============================================================================

class RetrievedChunk(BaseModel):
    """A single chunk retrieved from Qdrant with its similarity score."""

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={"title": "RetrievedChunk"},
    )

    chunk_text: str = Field(..., description="Raw text of the chunk")
    score: float = Field(..., description="Cosine similarity score (0-1)")
    page_num: int = Field(default=0, description="Page number in source document")
    section_name: str = Field(default="", description="Section name from chunker")
    doc_type: str = Field(default="", description="Document type")
    chunk_index: int = Field(default=0, description="Position within document")
    embed_priority: str = Field(default="MEDIUM", description="Embedding priority level")
    source_file: str = Field(default="", description="Original filename")


# =============================================================================
# 5. EXTRACTION VALUE WITH PROVENANCE
# =============================================================================

class ExtractedValue(BaseModel):
    """
    A single financial figure with full provenance.

    Every value extracted by Claude includes:
      - The numeric value (normalized to Crores)
      - The year label as written in the document
      - The original unit before normalization
      - Source page and section for audit trail
    """

    model_config = ConfigDict(
        json_schema_extra={"title": "ExtractedValue"},
    )

    value: Optional[float] = Field(
        default=None, description="Numeric value normalized to Crores (null if not found)"
    )
    year_label: Optional[str] = Field(
        default=None, description="Year label as written in the document (e.g. 'FY2024')"
    )
    original_unit: Optional[str] = Field(
        default=None, description="Original unit in the document: 'Crores', 'Lakhs', 'Thousands'"
    )
    source_page: Optional[int] = Field(
        default=None, description="Page number where this figure was found"
    )
    source_section: Optional[str] = Field(
        default=None, description="Section name where this figure was found"
    )


# =============================================================================
# 6. CLAUDE EXTRACTION MODELS
# =============================================================================

class FinancialSummaryExtraction(BaseModel):
    """Structured financial data extracted by Claude from RAG chunks."""

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={"title": "FinancialSummaryExtraction"},
    )

    revenue: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Revenue: {fy_current, fy_previous, fy_two_years_ago} — each an ExtractedValue",
    )
    ebitda: Optional[Dict[str, Any]] = Field(
        default=None,
        description="EBITDA: {fy_current, fy_previous} — each an ExtractedValue",
    )
    pat: Optional[Dict[str, Any]] = Field(
        default=None,
        description="PAT: {fy_current, fy_previous} — each an ExtractedValue",
    )
    total_debt: Optional[ExtractedValue] = Field(
        default=None, description="Total outstanding debt"
    )
    net_worth: Optional[ExtractedValue] = Field(
        default=None, description="Net worth (shareholders' equity)"
    )
    current_assets: Optional[ExtractedValue] = Field(
        default=None, description="Total current assets"
    )
    current_liabilities: Optional[ExtractedValue] = Field(
        default=None, description="Total current liabilities"
    )
    ebit: Optional[ExtractedValue] = Field(
        default=None, description="EBIT (Earnings Before Interest & Taxes)"
    )
    interest_expense: Optional[ExtractedValue] = Field(
        default=None, description="Total interest/finance costs"
    )
    operating_cash_flow: Optional[ExtractedValue] = Field(
        default=None, description="Cash flow from operating activities"
    )
    debt_service: Optional[ExtractedValue] = Field(
        default=None, description="Total debt service (principal + interest)"
    )
    fiscal_year_end: Optional[str] = Field(
        default=None, description="Fiscal year end date, e.g. '31-Mar-2024'"
    )
    extraction_notes: Optional[str] = Field(
        default=None, description="Ambiguity, merged cells, or uncertainty observed"
    )
    extraction_model: str = Field(
        default="", description="Model used for extraction"
    )
    status: str = Field(default="success", description="Extraction status")


class QualitativeExtraction(BaseModel):
    """Qualitative signals: auditor notes, litigation, management commentary."""

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={"title": "QualitativeExtraction"},
    )

    auditor_qualification: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Auditor qualification: {has_qualification, qualification_text, qualification_type, source_page}",
    )
    going_concern_flag: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Going concern: {mentioned, context, source_page}",
    )
    litigation_disclosures: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Litigation items: [{description, amount_crore, status, source_page}]",
    )
    management_commentary_summary: Optional[str] = Field(
        default=None, description="Summary of management discussion & analysis"
    )
    key_risks_mentioned: List[str] = Field(
        default_factory=list, description="Key risks mentioned in the document"
    )
    extraction_notes: Optional[str] = Field(
        default=None, description="Extraction notes and caveats"
    )
    extraction_model: str = Field(default="", description="Model used")
    status: str = Field(default="success", description="Extraction status")


class CovenantExtraction(BaseModel):
    """Covenant and collateral information."""

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={"title": "CovenantExtraction"},
    )

    existing_covenants: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Covenants: [{covenant_description, lender, threshold_value, breach_status, source_page, source_doc_type}]",
    )
    collateral_items: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Collateral: [{description, type, estimated_value_crore, charge_type, source_page}]",
    )
    extraction_notes: Optional[str] = Field(
        default=None, description="Extraction notes"
    )
    extraction_model: str = Field(default="", description="Model used")
    status: str = Field(default="success", description="Extraction status")


class RatingExtraction(BaseModel):
    """Rating agency intelligence."""

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={"title": "RatingExtraction"},
    )

    current_rating: Optional[str] = Field(
        default=None, description="Current credit rating, e.g. 'CRISIL BBB+'"
    )
    rating_agency: Optional[str] = Field(
        default=None, description="Rating agency name"
    )
    rating_date: Optional[str] = Field(
        default=None, description="Date the rating was assigned"
    )
    rating_outlook: Optional[str] = Field(
        default=None, description="Rating outlook: 'Stable', 'Positive', 'Negative', 'Watch'"
    )
    previous_rating: Optional[str] = Field(
        default=None, description="Previous credit rating"
    )
    rating_action: Optional[str] = Field(
        default=None, description="Rating action: 'Upgraded', 'Downgraded', 'Reaffirmed', 'Withdrawn'"
    )
    key_strengths: List[str] = Field(
        default_factory=list, description="Key strengths cited by rating agency"
    )
    key_weaknesses: List[str] = Field(
        default_factory=list, description="Key weaknesses cited by rating agency"
    )
    rationale_summary: Optional[str] = Field(
        default=None, description="Summary of rating rationale"
    )
    source_page: Optional[int] = Field(
        default=None, description="Source page for rating information"
    )
    extraction_model: str = Field(default="", description="Model used")
    status: str = Field(default="success", description="Extraction status")


# =============================================================================
# 7. COMBINED EXTRACTION RESULT
# =============================================================================

class RAGExtractionResult(BaseModel):
    """Combined result from all 4 extraction functions."""

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={"title": "RAGExtractionResult"},
    )

    job_id: str = Field(..., description="Loan application job ID")
    financial_summary: Optional[FinancialSummaryExtraction] = Field(
        default=None, description="Financial figures extracted by Claude"
    )
    qualitative_signals: Optional[QualitativeExtraction] = Field(
        default=None, description="Qualitative signals extracted by Claude"
    )
    covenant_collateral: Optional[CovenantExtraction] = Field(
        default=None, description="Covenant and collateral info"
    )
    rating_intelligence: Optional[RatingExtraction] = Field(
        default=None, description="Rating agency intelligence"
    )
    extraction_model: str = Field(
        default=CLAUDE_RAG_EXTRACTION_MODEL,
        description="Claude model used for all extraction calls",
    )
    status: Literal["success", "partial", "failed"] = Field(
        default="success", description="Overall extraction status"
    )
    errors: List[str] = Field(
        default_factory=list, description="Error messages from failed extractions"
    )
    extracted_at: str = Field(
        default="", description="ISO timestamp of extraction completion"
    )


# =============================================================================
# 8. QUERY MODELS
# =============================================================================

class QueryRequest(BaseModel):
    """POST /api/v1/rag/query request body."""

    model_config = ConfigDict(
        json_schema_extra={"title": "QueryRequest"},
    )

    job_id: str = Field(..., description="Loan application job ID")
    query: str = Field(..., description="Free-form question to search for")
    top_k: int = Field(
        default=5, ge=1, le=20, description="Number of top results to return"
    )
    doc_type_filter: Optional[str] = Field(
        default=None, description="Filter to a specific doc_type (null = search all)"
    )


class QueryResponse(BaseModel):
    """Response from ad-hoc semantic search."""

    model_config = ConfigDict(
        json_schema_extra={"title": "QueryResponse"},
    )

    job_id: str = Field(..., description="Loan application job ID")
    query: str = Field(..., description="Original query string")
    results: List[RetrievedChunk] = Field(
        default_factory=list, description="Ranked list of retrieved chunks"
    )
    result_count: int = Field(default=0, description="Number of results returned")
