"""
Fraud Detector — NetworkX graph traversals for fraud pattern detection.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

import networkx as nx

from .schemas import FraudFlag, FraudDetectionResult
from .graph_store import (
    get_graph,
    COMPANY,
    PERSON,
    APPLICATION,
    PAID_TO,
    DIRECTOR_OF,
    SUBSIDIARY_OF,
    APPLIED_FOR,
)

logger = logging.getLogger("entity_graph.fraud_detector")

_BASE_PATH = Path("/tmp/intelli-credit")

_SEVERITY_RANK = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1, "NONE": 0}


def _highest_severity(flags: List[FraudFlag]) -> str:
    if not flags:
        return "NONE"
    return max(flags, key=lambda f: _SEVERITY_RANK.get(f.severity, 0)).severity


# =============================================================================
# Helper logic for extracting edges of a specific type
# =============================================================================

def _get_edges_by_type(G: nx.MultiDiGraph, u: str, v: str, edge_type: str) -> list:
    """Helper to find all edge datas between u and v that match a type."""
    matches = []
    if G.has_edge(u, v):
        for key, data in G[u][v].items():
            if data.get("type") == edge_type:
                matches.append(data)
    return matches


# =============================================================================
# Fraud Detection Functions (NetworkX implementations)
# =============================================================================

def detect_related_party_director_overlap(
    G: nx.MultiDiGraph, job_id: str, borrower_name: str
) -> Optional[FraudFlag]:
    """
    Detect: A supplier of the borrower shares a director with the borrower.
    Cypher: 
      MATCH (borrower)-[r:PAID_TO]->(supplier) 
      MATCH (supplier)<-[:DIRECTOR_OF]-(shared_director) 
      MATCH (shared_director)-[:DIRECTOR_OF]->(borrower)
    """
    if not G.has_node(borrower_name):
        return None
        
    for supplier in G.successors(borrower_name):
        paid_edges = _get_edges_by_type(G, borrower_name, supplier, PAID_TO)
        if not paid_edges:
            continue
            
        # Found a supplier we paid. Now check for shared directors
        # Directors are predecessors of borrower via DIRECTOR_OF
        borrower_directors = set()
        for d in G.predecessors(borrower_name):
            if _get_edges_by_type(G, d, borrower_name, DIRECTOR_OF):
                borrower_directors.add(d)

        for d in borrower_directors:
            if _get_edges_by_type(G, d, supplier, DIRECTOR_OF):
                # Found overlap
                amount = max([e.get("amount_crore", 0) for e in paid_edges])
                
                logger.warning(
                    f"[{job_id}] FRAUD: Director overlap — {d} is director of "
                    f"both {borrower_name} and supplier {supplier}"
                )

                return FraudFlag(
                    flag_type="RELATED_PARTY_DIRECTOR_OVERLAP",
                    severity="CRITICAL",
                    score_penalty=-25,
                    description=(f"{d} is director of both {borrower_name} and its supplier {supplier}. Payment: ₹{amount}Cr"),
                    evidence={"director": d, "supplier": supplier, "amount_crore": amount},
                    source="Entity Graph — NetworkX traversal",
                )

    return None


def detect_historical_rejection(
    G: nx.MultiDiGraph, job_id: str, borrower_name: str
) -> Optional[FraudFlag]:
    """
    Detect: The same company or a company sharing a director has been
    rejected in a previous Intelli-Credit application.
    """
    if not G.has_node(borrower_name):
        return None

    def _is_rejected_app(app_id):
        return G.has_node(app_id) and G.nodes[app_id].get("decision") == "REJECT"

    # 1. Direct rejection
    for app in G.successors(borrower_name):
        if _get_edges_by_type(G, borrower_name, app, APPLIED_FOR):
            if app != job_id and _is_rejected_app(app):
                prev_comp = G.nodes[app].get("borrower_name", borrower_name)
                logger.warning(f"[{job_id}] FRAUD: Direct historical rejection — {borrower_name} was rejected in {app}")
                return FraudFlag(
                    flag_type="HISTORICAL_REJECTION_MATCH",
                    severity="HIGH",
                    score_penalty=-15,
                    description=f"{borrower_name} was previously rejected in application {app}",
                    evidence={"previous_job_id": app, "previous_company": prev_comp, "match_type": "direct"},
                    source="Entity Graph — NetworkX cross-app query",
                )

    # 2. Director-linked rejection
    for d in G.predecessors(borrower_name):
        if _get_edges_by_type(G, d, borrower_name, DIRECTOR_OF):
            for other_comp in G.successors(d):
                if other_comp != borrower_name and _get_edges_by_type(G, d, other_comp, DIRECTOR_OF):
                    for app in G.successors(other_comp):
                        if _get_edges_by_type(G, other_comp, app, APPLIED_FOR):
                            if app != job_id and _is_rejected_app(app):
                                logger.warning(f"[{job_id}] FRAUD: Director-linked rejection — {d} linked to rejected {other_comp} ({app})")
                                return FraudFlag(
                                    flag_type="HISTORICAL_REJECTION_MATCH",
                                    severity="HIGH",
                                    score_penalty=-15,
                                    description=f"Director {d} linked to previously rejected application {app} ({other_comp})",
                                    evidence={"shared_director": d, "rejected_company": other_comp, "previous_job_id": app, "match_type": "director_linked"},
                                    source="Entity Graph — NetworkX cross-app query",
                                )
    return None


def detect_shell_supplier_network(
    G: nx.MultiDiGraph, job_id: str, borrower_name: str
) -> Optional[FraudFlag]:
    """
    Detect: Multiple suppliers of the borrower share the same director.
    """
    if not G.has_node(borrower_name):
        return None
        
    # Find all suppliers
    suppliers = []
    for s in G.successors(borrower_name):
        if _get_edges_by_type(G, borrower_name, s, PAID_TO):
            suppliers.append(s)
            
    # Group suppliers by director
    director_suppliers = {}
    for supplier in suppliers:
        for d in G.predecessors(supplier):
            if _get_edges_by_type(G, d, supplier, DIRECTOR_OF):
                if d not in director_suppliers:
                    director_suppliers[d] = []
                director_suppliers[d].append(supplier)
                
    # Check for >= 2
    for d, controlled in director_suppliers.items():
        if len(controlled) >= 2:
            logger.warning(f"[{job_id}] FRAUD: Shell network — {d} controls {len(controlled)} suppliers: {controlled}")
            return FraudFlag(
                flag_type="SHELL_SUPPLIER_NETWORK",
                severity="HIGH",
                score_penalty=-20,
                description=f"{d} controls {len(controlled)} suppliers of the borrower: {', '.join(controlled)}",
                evidence={"controller": d, "suppliers": controlled},
                source="Entity Graph — shell network NetworkX",
            )
            
    return None


def detect_circular_ownership(
    G: nx.MultiDiGraph, job_id: str, borrower_name: str
) -> Optional[FraudFlag]:
    """
    Detect: A subsidiary of the borrower is also a supplier to the borrower
    """
    if not G.has_node(borrower_name):
        return None
        
    for sub in G.predecessors(borrower_name):
        if _get_edges_by_type(G, sub, borrower_name, SUBSIDIARY_OF):
            if _get_edges_by_type(G, borrower_name, sub, PAID_TO):
                logger.warning(f"[{job_id}] FRAUD: Circular ownership — {sub} is both subsidiary and supplier of {borrower_name}")
                return FraudFlag(
                    flag_type="CIRCULAR_OWNERSHIP_PAYMENT",
                    severity="HIGH",
                    score_penalty=-20,
                    description=f"{sub} is both a subsidiary of and a paid supplier to the borrower",
                    evidence={"circular_entity": sub, "borrower": borrower_name},
                    source="Entity Graph — circular ownership NetworkX",
                )
    return None


# =============================================================================
# Orchestrator
# =============================================================================

async def run_all_fraud_checks(
    driver, job_id: str, borrower_name: str
) -> FraudDetectionResult:
    """
    Run all 4 fraud detection checks over NetworkX and write results to disk.
    NOTE: driver is ignored, kept in signature for compat or typing limits.
    """
    import asyncio
    
    G = get_graph()
    
    # Resolve borrower name just like exporter did
    resolved_name = borrower_name
    if not G.has_node(borrower_name):
        for node in G.nodes():
            if isinstance(node, str):
                if node.startswith("Unknown-") and node.endswith(job_id):
                    resolved_name = node
                    break
                if borrower_name.lower() in node.lower() and not node.startswith("Unknown-"):
                    if COMPANY in G.nodes[node].get("labels", []):
                        resolved_name = node
                        break
                        
    if resolved_name != borrower_name:
        borrower_name = resolved_name

    checks = [
        ("related_party_director_overlap", detect_related_party_director_overlap),
        ("historical_rejection", detect_historical_rejection),
        ("shell_supplier_network", detect_shell_supplier_network),
        ("circular_ownership", detect_circular_ownership),
    ]

    flags: List[FraudFlag] = []

    def _run_checks():
        for check_name, check_fn in checks:
            try:
                flag = check_fn(G, job_id, borrower_name)
                if flag is not None:
                    flags.append(flag)
            except Exception as e:
                logger.error(f"[{job_id}] Fraud check '{check_name}' failed: {e}")

    await asyncio.to_thread(_run_checks)

    now = datetime.now(timezone.utc).isoformat()

    result = FraudDetectionResult(
        job_id=job_id,
        borrower_name=borrower_name,
        flags=flags,
        total_score_penalty=sum(f.score_penalty for f in flags),
        highest_severity=_highest_severity(flags),
        checked_at=now,
    )

    output_dir = _BASE_PATH / job_id
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / "entity_fraud_flags.json"
    output_file.write_text(
        result.model_dump_json(indent=2), encoding="utf-8"
    )

    logger.info(
        f"[{job_id}] Fraud detection complete: "
        f"{len(flags)} flags, penalty={result.total_score_penalty}, "
        f"severity={result.highest_severity} → {output_file}"
    )

    return result
