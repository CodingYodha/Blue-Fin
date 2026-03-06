"""
Pydantic v2 schemas for the Entity Graph module.

All models used across graph_writer, fuzzy_matcher, fraud_detector,
graph_exporter, and routes are defined here as the single source of truth.

Models:
  1. WriteResult            — graph_writer output
  2. EntityMatchResult      — fuzzy_matcher single match
  3. TransactionLinkResult  — fuzzy_matcher aggregate result
  4. FraudFlag              — single fraud detection finding
  5. FraudDetectionResult   — aggregate fraud detection output
  6. GraphNode              — frontend graph node
  7. GraphEdge              — frontend graph edge
  8. GraphExport            — frontend graph export
  9. BuildGraphRequest      — POST /entity-graph/build body
  10. SetDecisionRequest    — POST /entity-graph/{job_id}/set-decision body
"""

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


# =============================================================================
# 1. GRAPH WRITER
# =============================================================================

class WriteResult(BaseModel):
    """Result of writing entities to the Neo4j graph."""

    model_config = ConfigDict(from_attributes=True)

    job_id: str = Field(..., description="Job ID for this graph write")
    nodes_written: int = Field(
        default=0, description="Count of MERGE node operations executed"
    )
    relationships_written: int = Field(
        default=0, description="Count of MERGE relationship operations executed"
    )
    status: Literal["success", "failed"] = Field(
        default="success", description="Whether the graph write succeeded"
    )
    error: Optional[str] = Field(
        default=None, description="Error message if status is 'failed'"
    )


# =============================================================================
# 2-3. FUZZY MATCHER
# =============================================================================

class EntityMatchResult(BaseModel):
    """A single fuzzy match result between an entity and a transaction."""

    model_config = ConfigDict(from_attributes=True)

    entity_name: str = Field(
        ..., description="Original NER entity name"
    )
    matched_description: str = Field(
        ..., description="Bank transaction description that matched"
    )
    score: int = Field(
        ..., description="Fuzzy match score (0-100)"
    )
    confidence: Literal["CONFIRMED_MATCH", "PROBABLE_MATCH", "NO_MATCH"] = Field(
        ..., description="Match confidence based on score thresholds"
    )


class TransactionLinkResult(BaseModel):
    """Summary of fuzzy-match linking across all entities and transactions."""

    model_config = ConfigDict(from_attributes=True)

    confirmed_links: int = Field(
        default=0, description="Number of CONFIRMED_MATCH relationships written"
    )
    probable_links: int = Field(
        default=0, description="Number of PROBABLE_MATCH relationships written"
    )
    entities_checked: int = Field(
        default=0, description="Total NER entity names checked"
    )
    transactions_checked: int = Field(
        default=0, description="Total transaction descriptions checked"
    )


# =============================================================================
# 4-5. FRAUD DETECTOR
# =============================================================================

class FraudFlag(BaseModel):
    """A single detected fraud pattern."""

    model_config = ConfigDict(from_attributes=True)

    flag_type: str = Field(
        ...,
        description=(
            "Fraud pattern identifier: RELATED_PARTY_DIRECTOR_OVERLAP, "
            "HISTORICAL_REJECTION_MATCH, SHELL_SUPPLIER_NETWORK, "
            "CIRCULAR_OWNERSHIP_PAYMENT"
        ),
    )
    severity: Literal["CRITICAL", "HIGH", "MEDIUM", "LOW"] = Field(
        ..., description="Severity of the fraud signal"
    )
    score_penalty: int = Field(
        ..., description="Negative score penalty applied to the credit score"
    )
    description: str = Field(
        ..., description="Human-readable description of the fraud pattern detected"
    )
    evidence: Dict[str, Any] = Field(
        default_factory=dict,
        description="Key evidence data points (director names, amounts, etc.)",
    )
    source: str = Field(
        default="Entity Graph — Neo4j Cypher traversal",
        description="Source module/method that detected this flag",
    )


class FraudDetectionResult(BaseModel):
    """Aggregate result of all fraud checks for a single application."""

    model_config = ConfigDict(from_attributes=True)

    job_id: str = Field(..., description="Job ID of the application checked")
    borrower_name: str = Field(
        ..., description="Primary borrower company name"
    )
    flags: List[FraudFlag] = Field(
        default_factory=list, description="All detected fraud flags"
    )
    total_score_penalty: int = Field(
        default=0, description="Sum of all flag score penalties"
    )
    highest_severity: Literal["CRITICAL", "HIGH", "MEDIUM", "NONE"] = Field(
        default="NONE",
        description="Highest severity across all flags",
    )
    checked_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="UTC timestamp of when the checks were run",
    )


# =============================================================================
# 6-8. GRAPH EXPORTER
# =============================================================================

class GraphNode(BaseModel):
    """A single node in the frontend graph visualization."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Neo4j element ID (string)")
    label: str = Field(..., description="Display name (company or person name)")
    type: Literal["COMPANY", "PERSON", "LOAN", "APPLICATION"] = Field(
        ..., description="Node type"
    )
    is_borrower: bool = Field(
        default=False, description="True if this is the primary borrower company"
    )
    is_flagged: bool = Field(
        default=False, description="True if involved in a fraud flag"
    )
    flag_type: Optional[str] = Field(
        default=None,
        description="Fraud flag type if flagged, e.g. RELATED_PARTY_DIRECTOR_OVERLAP",
    )
    properties: Dict[str, Any] = Field(
        default_factory=dict, description="All Neo4j node properties"
    )


class GraphEdge(BaseModel):
    """A single edge in the frontend graph visualization."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Neo4j relationship element ID (string)")
    source: str = Field(..., description="Source node element ID")
    target: str = Field(..., description="Target node element ID")
    type: str = Field(
        ..., description="Relationship type, e.g. PAID_TO, DIRECTOR_OF"
    )
    label: str = Field(
        ...,
        description="Human-readable label, e.g. 'Paid ₹4.2Cr' or 'Director of'",
    )
    is_flagged: bool = Field(
        default=False, description="True if this edge is part of a fraud flag"
    )
    properties: Dict[str, Any] = Field(
        default_factory=dict, description="Relationship properties (amount, date, etc.)"
    )


class GraphExport(BaseModel):
    """Complete graph export for the frontend force-directed visualization."""

    model_config = ConfigDict(from_attributes=True)

    job_id: str = Field(..., description="Job ID this graph belongs to")
    nodes: List[GraphNode] = Field(
        default_factory=list, description="All graph nodes"
    )
    edges: List[GraphEdge] = Field(
        default_factory=list, description="All graph edges"
    )
    node_count: int = Field(
        default=0, description="Total number of nodes"
    )
    edge_count: int = Field(
        default=0, description="Total number of edges"
    )
    generated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="UTC timestamp of when the export was generated",
    )


# =============================================================================
# 9-10. API REQUEST MODELS
# =============================================================================

class BuildGraphRequest(BaseModel):
    """POST /api/v1/entity-graph/build request body."""

    model_config = ConfigDict(from_attributes=True)

    job_id: str = Field(
        ..., description="Job ID from the document processing pipeline"
    )
    borrower_name: str = Field(
        ..., description="Primary borrower company name"
    )
    entity_extraction_path: str = Field(
        ...,
        description=(
            "Path to ocr_output.json written by Section 3, "
            "e.g. /tmp/intelli-credit/{job_id}/ocr_output.json"
        ),
    )


class SetDecisionRequest(BaseModel):
    """POST /api/v1/entity-graph/{job_id}/set-decision request body."""

    model_config = ConfigDict(from_attributes=True)

    decision: Literal["APPROVE", "CONDITIONAL", "REJECT"] = Field(
        ..., description="Final credit decision from the LightGBM scoring pipeline"
    )
    score: int = Field(
        ..., description="Final credit score (0-100)"
    )
