"""
Entity Graph Writer — writes EntityExtraction data into NetworkX.

Takes the EntityExtraction output from info_extractor.py and upserts all
entities and relationships into the NetworkX graph. Re-running
for the same company/job will update existing nodes/edges.
"""

import logging
from datetime import datetime
from typing import Optional

import networkx as nx

from deep_learning.schemas import EntityExtraction
from .schemas import WriteResult
from .graph_store import (
    get_graph,
    save_graph,
    PERSON,
    COMPANY,
    LOAN,
    APPLICATION,
    DIRECTOR_OF,
    GUARANTOR_FOR,
    SUBSIDIARY_OF,
    LENDER_TO,
    PAID_TO,
    APPLIED_FOR,
)

logger = logging.getLogger("entity_graph.graph_writer")


# =============================================================================
# Helper function for matching MERGE behavior
# =============================================================================

def _upsert_node(G: nx.MultiDiGraph, node_id: str, labels: list[str], properties: dict) -> bool:
    """Upserts a node into NetworkX graph. Uses name/job_id as the canonical node_id."""
    is_new = not G.has_node(node_id)
    if is_new:
        G.add_node(node_id, labels=labels, **properties)
    else:
        # Update existing properties
        nx.set_node_attributes(G, {node_id: properties})
    return is_new


def _upsert_edge(G: nx.MultiDiGraph, src_id: str, dst_id: str, type: str, properties: dict) -> bool:
    """Upserts an edge into NetworkX MultiDiGraph, preventing duplicate edges of same type."""
    is_new = True
    if G.has_edge(src_id, dst_id):
        # Check if an edge of this type already exists 
        # MultiDiGraph allows multiple edges, we enforce unique (src, dst, type)
        for key, edge_data in G[src_id][dst_id].items():
            if edge_data.get("type") == type:
                # Update existing edge
                is_new = False
                properties["type"] = type
                nx.set_edge_attributes(G, {(src_id, dst_id, key): properties})
                break
    
    if is_new:
        properties["type"] = type
        G.add_edge(src_id, dst_id, **properties)
    
    return is_new


# =============================================================================
# Individual write functions 
# =============================================================================

def write_application_node(G: nx.MultiDiGraph, job_id: str, borrower_name: str) -> int:
    is_new = _upsert_node(G, job_id, [APPLICATION], {"job_id": job_id, "borrower_name": borrower_name, "created_at": datetime.now().isoformat()})
    return 1 if is_new else 0


def write_borrower_node(G: nx.MultiDiGraph, company_name: str, cin: Optional[str]) -> int:
    is_new = _upsert_node(G, company_name, [COMPANY], {"name": company_name, "cin": cin, "last_seen": datetime.now().isoformat()})
    return 1 if is_new else 0


def write_promoters(G: nx.MultiDiGraph, promoters: list, company_name: str) -> tuple[int, int]:
    nodes = 0
    rels = 0
    for p in promoters:
        # P -> C
        if _upsert_node(G, p.name, [PERSON], {"name": p.name, "designation": p.designation, "din": p.din}):
            nodes += 1
        _upsert_node(G, company_name, [COMPANY], {"name": company_name}) # Ensure C exists
        
        if _upsert_edge(G, p.name, company_name, DIRECTOR_OF, {}):
            rels += 1
    return nodes, rels


def write_related_parties(G: nx.MultiDiGraph, related_parties: list, borrower_name: str) -> tuple[int, int]:
    nodes = 0
    rels = 0
    for rp in related_parties:
        if _upsert_node(G, rp.name, [COMPANY], {"name": rp.name, "flagged_as_related_party": True}):
            nodes += 1
        _upsert_node(G, borrower_name, [COMPANY], {"name": borrower_name})
        
        props = {
            "amount_crore": rp.transaction_amount_crore or 0.0,
            "relationship": rp.relationship or "unknown",
            "written_at": datetime.now().isoformat()
        }
        if _upsert_edge(G, borrower_name, rp.name, PAID_TO, props):
            rels += 1
    return nodes, rels


def write_subsidiaries(G: nx.MultiDiGraph, subsidiaries: list, borrower_name: str) -> tuple[int, int]:
    nodes = 0
    rels = 0
    for s in subsidiaries:
        if _upsert_node(G, s.name, [COMPANY], {"name": s.name, "cin": s.cin}):
            nodes += 1
        _upsert_node(G, borrower_name, [COMPANY], {"name": borrower_name})
        
        if _upsert_edge(G, s.name, borrower_name, SUBSIDIARY_OF, {}):
            rels += 1
    return nodes, rels


def write_lenders(G: nx.MultiDiGraph, lenders: list, borrower_name: str) -> tuple[int, int]:
    nodes = 0
    rels = 0
    for l in lenders:
        if _upsert_node(G, l.bank_name, [COMPANY], {"name": l.bank_name, "is_bank": True}):
            nodes += 1
        _upsert_node(G, borrower_name, [COMPANY], {"name": borrower_name})
        
        props = {
            "facility": l.facility_type or "unknown",
            "amount_crore": l.amount_crore or 0.0
        }
        if _upsert_edge(G, l.bank_name, borrower_name, LENDER_TO, props):
            rels += 1
    return nodes, rels


def write_guarantors(G: nx.MultiDiGraph, guarantors: list, borrower_name: str) -> tuple[int, int]:
    nodes = 0
    rels = 0
    for g in guarantors:
        if _upsert_node(G, g.name, [PERSON], {"name": g.name, "relationship": g.relationship_to_borrower}):
            nodes += 1
        
        loan_id = f"loan-{borrower_name}"
        if _upsert_node(G, loan_id, [LOAN], {"borrower": borrower_name}):
            nodes += 1
            
        if _upsert_edge(G, g.name, loan_id, GUARANTOR_FOR, {}):
            rels += 1
    return nodes, rels


def write_application_link(G: nx.MultiDiGraph, borrower_name: str, job_id: str) -> int:
    _upsert_node(G, borrower_name, [COMPANY], {"name": borrower_name})
    _upsert_node(G, job_id, [APPLICATION], {"job_id": job_id})
    if _upsert_edge(G, borrower_name, job_id, APPLIED_FOR, {}):
        return 1
    return 0


# =============================================================================
# Orchestrator
# =============================================================================

def _execute_all_writes(
    G: nx.MultiDiGraph,
    entity_data: EntityExtraction,
    job_id: str,
    borrower_name: str,
) -> tuple[int, int]:
    """Execute all graph writes in the NetworkX object."""
    total_nodes = 0
    total_rels = 0

    total_nodes += write_application_node(G, job_id, borrower_name)
    total_nodes += write_borrower_node(G, borrower_name, entity_data.cin)

    if entity_data.promoters:
        n, r = write_promoters(G, entity_data.promoters, borrower_name)
        total_nodes += n
        total_rels += r

    if entity_data.related_parties:
        n, r = write_related_parties(G, entity_data.related_parties, borrower_name)
        total_nodes += n
        total_rels += r

    if entity_data.subsidiaries:
        n, r = write_subsidiaries(G, entity_data.subsidiaries, borrower_name)
        total_nodes += n
        total_rels += r

    if entity_data.existing_lenders:
        n, r = write_lenders(G, entity_data.existing_lenders, borrower_name)
        total_nodes += n
        total_rels += r

    if entity_data.guarantors:
        n, r = write_guarantors(G, entity_data.guarantors, borrower_name)
        total_nodes += n
        total_rels += r

    total_rels += write_application_link(G, borrower_name, job_id)

    return total_nodes, total_rels


async def write_entity_graph(
    entity_data: EntityExtraction,
    job_id: str,
    borrower_name_override: Optional[str] = None,
) -> WriteResult:
    """
    Write all entities and relationships from EntityExtraction into NetworkX.
    """
    import asyncio

    borrower_name = entity_data.company_name or borrower_name_override or f"Unknown-{job_id}"

    try:
        G = get_graph()

        def _run_write():
            return _execute_all_writes(
                G,
                entity_data=entity_data,
                job_id=job_id,
                borrower_name=borrower_name,
            )

        total_nodes, total_rels = await asyncio.to_thread(_run_write)
        
        # Save to disk after writes
        save_graph()

        logger.info(
            f"[{job_id}] Graph write complete: "
            f"{total_nodes} new nodes, {total_rels} new relationships "
            f"(borrower={borrower_name})"
        )

        return WriteResult(
            job_id=job_id,
            nodes_written=total_nodes,
            relationships_written=total_rels,
            status="success",
        )

    except Exception as e:
        logger.error(f"[{job_id}] Graph write failed: {e}")
        import traceback
        traceback.print_exc()
        return WriteResult(
            job_id=job_id,
            nodes_written=0,
            relationships_written=0,
            status="failed",
            error=str(e),
        )

