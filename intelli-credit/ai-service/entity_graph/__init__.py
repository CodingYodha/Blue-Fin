"""
Entity Graph module — Neo4j-backed entity relationship graph for Intelli-Credit.

Sub-modules:
  - schemas        : All Pydantic v2 models (single source of truth)
  - neo4j_client   : Connection singleton, schema constants, constraints, health check
  - graph_writer   : Writes EntityExtraction into Neo4j (MERGE/upsert)
  - fuzzy_matcher  : V12 fix — fuzzy entity-to-transaction matching
  - fraud_detector : Cypher-based cross-application fraud detection
  - graph_exporter : Frontend-ready {nodes, edges} JSON export
  - routes         : FastAPI APIRouter with 4 endpoints
"""

from .neo4j_client import (
    get_driver,
    close_driver,
    create_constraints,
    neo4j_health_check,
    PERSON,
    COMPANY,
    LOAN,
    APPLICATION,
    DIRECTOR_OF,
    GUARANTOR_FOR,
    SUPPLIER_TO,
    SUBSIDIARY_OF,
    LENDER_TO,
    PAID_TO,
    APPLIED_FOR,
    FLAGGED_IN,
)
from .schemas import (
    WriteResult,
    EntityMatchResult,
    TransactionLinkResult,
    FraudFlag,
    FraudDetectionResult,
    GraphNode,
    GraphEdge,
    GraphExport,
    BuildGraphRequest,
    SetDecisionRequest,
)
from .graph_writer import write_entity_graph
from .fuzzy_matcher import (
    normalize_entity_name,
    match_score,
    classify_match,
    find_entity_in_transactions,
    link_transactions_to_graph,
    MatchConfidence,
)
from .fraud_detector import (
    run_all_fraud_checks,
    detect_related_party_director_overlap,
    detect_historical_rejection,
    detect_shell_supplier_network,
    detect_circular_ownership,
)
from .graph_exporter import export_graph_for_ui

__all__ = [
    "get_driver",
    "close_driver",
    "create_constraints",
    "neo4j_health_check",
    "write_entity_graph",
    "WriteResult",
    "normalize_entity_name",
    "match_score",
    "classify_match",
    "find_entity_in_transactions",
    "link_transactions_to_graph",
    "MatchConfidence",
    "EntityMatchResult",
    "TransactionLinkResult",
    "run_all_fraud_checks",
    "FraudFlag",
    "FraudDetectionResult",
    "export_graph_for_ui",
    "GraphNode",
    "GraphEdge",
    "GraphExport",
    "PERSON",
    "COMPANY",
    "LOAN",
    "APPLICATION",
    "DIRECTOR_OF",
    "GUARANTOR_FOR",
    "SUPPLIER_TO",
    "SUBSIDIARY_OF",
    "LENDER_TO",
    "PAID_TO",
    "APPLIED_FOR",
    "FLAGGED_IN",
]
