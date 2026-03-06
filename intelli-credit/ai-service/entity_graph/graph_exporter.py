"""
Graph Exporter — produces frontend-ready {nodes, edges} JSON from Neo4j.

=============================================================================
The Next.js frontend renders an interactive force-directed graph.  This module
queries Neo4j, deduplicates nodes, cross-references fraud flags from
entity_fraud_flags.json, and exports a clean GraphExport that the frontend
can consume directly — no Neo4j knowledge required on the frontend side.

Output:
  GraphExport → written to /tmp/intelli-credit/{job_id}/entity_graph.json
=============================================================================
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from .schemas import GraphNode, GraphEdge, GraphExport
from .neo4j_client import (
    COMPANY,
    PERSON,
    LOAN,
    APPLICATION,
    DIRECTOR_OF,
    LENDER_TO,
    PAID_TO,
    SUBSIDIARY_OF,
    GUARANTOR_FOR,
    APPLIED_FOR,
    FLAGGED_IN,
)

logger = logging.getLogger("entity_graph.graph_exporter")

# Shared volume base path
_BASE_PATH = Path("/tmp/intelli-credit")


# =============================================================================
# Human-readable edge labels
# =============================================================================

def _edge_label(rel_type: str, props: Dict[str, Any]) -> str:
    """Generate a human-readable label for an edge."""
    amount = props.get("amount_crore")
    facility = props.get("facility")
    confidence = props.get("confidence")

    if rel_type == PAID_TO:
        base = f"Paid ₹{amount}Cr" if amount else "Paid"
        if confidence:
            base += f" ({confidence})"
        return base
    elif rel_type == DIRECTOR_OF:
        return "Director of"
    elif rel_type == LENDER_TO:
        base = f"Lender ({facility})" if facility else "Lender"
        if amount:
            base += f" ₹{amount}Cr"
        return base
    elif rel_type == SUBSIDIARY_OF:
        return "Subsidiary of"
    elif rel_type == GUARANTOR_FOR:
        return "Guarantor for"
    elif rel_type == APPLIED_FOR:
        return "Applied for"
    elif rel_type == FLAGGED_IN:
        reason = props.get("reason", "")
        return f"Flagged: {reason}" if reason else "Flagged"
    else:
        return rel_type.replace("_", " ").title()


# =============================================================================
# Node type detection
# =============================================================================

def _detect_node_type(labels: List[str]) -> str:
    """Determine the node type from Neo4j labels."""
    label_set = {l.upper() for l in labels} if labels else set()
    if PERSON in label_set:
        return PERSON
    if APPLICATION in label_set:
        return APPLICATION
    if LOAN in label_set:
        return LOAN
    return COMPANY  # default


# =============================================================================
# Fraud flag cross-referencing
# =============================================================================

def _load_fraud_flags(job_id: str) -> tuple[Set[str], Dict[str, str]]:
    """
    Load fraud flags and extract flagged entity names + their flag types.

    Returns:
        (flagged_names, name_to_flag_type) — sets/dicts of entity names
        involved in fraud flags.
    """
    fraud_file = _BASE_PATH / job_id / "entity_fraud_flags.json"
    flagged_names: Set[str] = set()
    name_to_flag: Dict[str, str] = {}

    if not fraud_file.exists():
        return flagged_names, name_to_flag

    try:
        data = json.loads(fraud_file.read_text(encoding="utf-8"))
        for flag in data.get("flags", []):
            flag_type = flag.get("flag_type", "")
            evidence = flag.get("evidence", {})

            # Collect all entity names from evidence
            for key in ("director", "supplier", "controller",
                        "circular_entity", "borrower", "rejected_company",
                        "shared_director"):
                name = evidence.get(key)
                if name:
                    flagged_names.add(name)
                    name_to_flag[name] = flag_type

            # Suppliers list
            for s in evidence.get("suppliers", []):
                flagged_names.add(s)
                name_to_flag[s] = flag_type

    except Exception as e:
        logger.warning(f"Failed to load fraud flags for {job_id}: {e}")

    return flagged_names, name_to_flag


# =============================================================================
# Main export function
# =============================================================================

async def export_graph_for_ui(
    driver, job_id: str, borrower_name: str
) -> GraphExport:
    """
    Query Neo4j for all nodes/edges connected to this application's borrower,
    deduplicate, cross-reference fraud flags, and export a clean JSON
    for the frontend force-directed graph.

    Writes to: /tmp/intelli-credit/{job_id}/entity_graph.json

    Args:
        driver:        Neo4j driver instance.
        job_id:        Current job ID.
        borrower_name: Primary borrower company name.

    Returns:
        GraphExport with deduplicated nodes and edges.
    """
    import asyncio

    query = (
        f"MATCH (borrower:{COMPANY} {{name: $borrower_name}}) "
        f"OPTIONAL MATCH (borrower)-[r1]->(related:{COMPANY}) "
        f"OPTIONAL MATCH (p:{PERSON})-[r2:{DIRECTOR_OF}]->(borrower) "
        f"OPTIONAL MATCH (p)-[r3:{DIRECTOR_OF}]->(related) "
        f"OPTIONAL MATCH (bank:{COMPANY})-[r4:{LENDER_TO}]->(borrower) "
        f"OPTIONAL MATCH (borrower)-[r5:{APPLIED_FOR}]->(app:{APPLICATION}) "
        f"OPTIONAL MATCH (g:{PERSON})-[r6:{GUARANTOR_FOR}]->(loan:{LOAN}) "
        f"WHERE loan.borrower = $borrower_name "
        f"RETURN borrower, related, p, bank, app, loan, g, "
        f"       r1, r2, r3, r4, r5, r6, "
        f"       labels(borrower) AS borrower_labels, "
        f"       labels(related) AS related_labels, "
        f"       labels(p) AS person_labels, "
        f"       labels(bank) AS bank_labels, "
        f"       labels(app) AS app_labels, "
        f"       labels(loan) AS loan_labels, "
        f"       labels(g) AS guarantor_labels"
    )

    def _run_query():
        with driver.session() as session:
            result = session.run(query, borrower_name=borrower_name)
            return [record.data() for record in result]

    records = await asyncio.to_thread(_run_query)

    # Load fraud flags
    flagged_names, name_to_flag = _load_fraud_flags(job_id)

    # Deduplicate nodes and edges
    nodes_by_id: Dict[str, GraphNode] = {}
    edges_by_id: Dict[str, GraphEdge] = {}

    def _add_node(node_obj, labels_key: str, record: dict):
        """Extract and deduplicate a node from a record."""
        if node_obj is None:
            return
        eid = str(node_obj.element_id)
        if eid in nodes_by_id:
            return

        props = dict(node_obj)
        name = props.get("name", props.get("job_id", props.get("borrower", f"node-{eid}")))
        labels = record.get(labels_key, [])
        node_type = _detect_node_type(labels)

        is_flagged = name in flagged_names
        flag_type = name_to_flag.get(name)

        nodes_by_id[eid] = GraphNode(
            id=eid,
            label=str(name),
            type=node_type,
            is_borrower=(name == borrower_name),
            is_flagged=is_flagged,
            flag_type=flag_type,
            properties=_sanitize_props(props),
        )

    def _add_edge(rel_obj):
        """Extract and deduplicate a relationship from a record."""
        if rel_obj is None:
            return
        eid = str(rel_obj.element_id)
        if eid in edges_by_id:
            return

        rel_type = rel_obj.type
        props = dict(rel_obj)
        source_id = str(rel_obj.start_node.element_id)
        target_id = str(rel_obj.end_node.element_id)

        # Check if either end is flagged
        source_name = dict(rel_obj.start_node).get("name", "")
        target_name = dict(rel_obj.end_node).get("name", "")
        is_flagged = source_name in flagged_names or target_name in flagged_names

        edges_by_id[eid] = GraphEdge(
            id=eid,
            source=source_id,
            target=target_id,
            type=rel_type,
            label=_edge_label(rel_type, props),
            is_flagged=is_flagged,
            properties=_sanitize_props(props),
        )

    # Process all records
    for record in records:
        # Nodes — the raw record from session.run().data() returns dicts,
        # but we need the actual node objects. Re-query with graph result.
        pass

    # Re-run with graph result format for proper node/relationship objects
    def _run_graph_query():
        with driver.session() as session:
            result = session.run(query, borrower_name=borrower_name)
            graph = result.graph()
            return list(graph.nodes), list(graph.relationships)

    all_nodes, all_rels = await asyncio.to_thread(_run_graph_query)

    # Process nodes
    for node in all_nodes:
        eid = str(node.element_id)
        if eid in nodes_by_id:
            continue

        props = dict(node)
        labels = list(node.labels)
        name = props.get("name", props.get("job_id", props.get("borrower", f"node-{eid}")))
        node_type = _detect_node_type(labels)

        is_flagged = str(name) in flagged_names
        flag_type = name_to_flag.get(str(name))

        nodes_by_id[eid] = GraphNode(
            id=eid,
            label=str(name),
            type=node_type,
            is_borrower=(str(name) == borrower_name),
            is_flagged=is_flagged,
            flag_type=flag_type,
            properties=_sanitize_props(props),
        )

    # Process relationships
    for rel in all_rels:
        eid = str(rel.element_id)
        if eid in edges_by_id:
            continue

        rel_type = rel.type
        props = dict(rel)
        source_id = str(rel.start_node.element_id)
        target_id = str(rel.end_node.element_id)

        source_name = str(dict(rel.start_node).get("name", ""))
        target_name = str(dict(rel.end_node).get("name", ""))
        is_flagged = source_name in flagged_names or target_name in flagged_names

        edges_by_id[eid] = GraphEdge(
            id=eid,
            source=source_id,
            target=target_id,
            type=rel_type,
            label=_edge_label(rel_type, props),
            is_flagged=is_flagged,
            properties=_sanitize_props(props),
        )

    export = GraphExport(
        job_id=job_id,
        nodes=list(nodes_by_id.values()),
        edges=list(edges_by_id.values()),
    )

    # Write to disk
    output_dir = _BASE_PATH / job_id
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / "entity_graph.json"
    output_file.write_text(
        export.model_dump_json(indent=2), encoding="utf-8"
    )

    logger.info(
        f"[{job_id}] Graph export: {len(export.nodes)} nodes, "
        f"{len(export.edges)} edges → {output_file}"
    )

    return export


def _sanitize_props(props: Dict[str, Any]) -> Dict[str, Any]:
    """Convert Neo4j property values to JSON-serializable types."""
    clean = {}
    for k, v in props.items():
        if v is None:
            continue
        if isinstance(v, (str, int, float, bool)):
            clean[k] = v
        elif isinstance(v, list):
            clean[k] = v
        else:
            clean[k] = str(v)
    return clean
