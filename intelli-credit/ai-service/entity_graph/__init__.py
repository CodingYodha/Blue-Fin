"""
Entity Graph module — Neo4j-backed entity relationship graph for Intelli-Credit.

Sub-modules:
  - neo4j_client  : Connection singleton, schema constants, constraints, health check
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
from .graph_writer import write_entity_graph, WriteResult

__all__ = [
    "get_driver",
    "close_driver",
    "create_constraints",
    "neo4j_health_check",
    "write_entity_graph",
    "WriteResult",
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
