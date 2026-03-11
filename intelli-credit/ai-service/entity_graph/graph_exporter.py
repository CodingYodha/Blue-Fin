"""
Graph Exporter — produces frontend-ready {nodes, edges} JSON from NetworkX.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

import networkx as nx

from .schemas import GraphNode, GraphEdge, GraphExport
from .graph_store import (
    get_graph,
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

_BASE_PATH = Path("/tmp/intelli-credit")


def _edge_label(rel_type: str, props: Dict[str, Any]) -> str:
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


def _detect_node_type(labels: List[str]) -> str:
    label_set = {l.upper() for l in labels} if labels else set()
    if PERSON in label_set:
        return PERSON
    if APPLICATION in label_set:
        return APPLICATION
    if LOAN in label_set:
        return LOAN
    return COMPANY


def _load_fraud_flags(job_id: str) -> Tuple[Set[str], Dict[str, str]]:
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

            for key in ("director", "supplier", "controller",
                        "circular_entity", "borrower", "rejected_company",
                        "shared_director"):
                name = evidence.get(key)
                if name:
                    flagged_names.add(name)
                    name_to_flag[name] = flag_type

            for s in evidence.get("suppliers", []):
                flagged_names.add(s)
                name_to_flag[s] = flag_type

    except Exception as e:
        logger.warning(f"Failed to load fraud flags for {job_id}: {e}")

    return flagged_names, name_to_flag


async def export_graph_for_ui(
    driver, job_id: str, borrower_name: str
) -> GraphExport:
    """
    Traverses NetworkX graph to extract 1-hop subgraph around borrower
    and returns frontend-ready GraphExport.
    """
    import asyncio
    
    flagged_names, name_to_flag = _load_fraud_flags(job_id)

    def _extract_graph():
        G = get_graph()
        
        # Resolve borrower name (exact match or partial matching like Cypher CONTAINS)
        resolved_name = borrower_name
        if not G.has_node(borrower_name):
            # Try finding unknown placeholder or substring
            for node in G.nodes():
                if isinstance(node, str):
                    if node.startswith("Unknown-") and node.endswith(job_id):
                        resolved_name = node
                        break
                    if borrower_name.lower() in node.lower() and not node.startswith("Unknown-"):
                        if COMPANY in G.nodes[node].get("labels", []):
                            resolved_name = node
                            break
        
        local_borrower_name = borrower_name
        if resolved_name != local_borrower_name:
            logger.info(f"[{job_id}] Resolved borrower name: '{local_borrower_name}' → '{resolved_name}'")
            local_borrower_name = resolved_name
            
        nodes_by_id: Dict[str, GraphNode] = {}
        edges_by_id: Dict[str, GraphEdge] = {}
        
        if not G.has_node(local_borrower_name):
            return nodes_by_id, edges_by_id
            
        # We need the ego graph with undirected steps = 1, since the Cypher query was:
        # OPTIONAL MATCH (p)-[:DIRECTOR_OF]->(borrower) etc
        ego_nodes = set([local_borrower_name])
        
        # Traversal logic equivalent to the Cypher MATCH
        # 1. Outgoing edges from borrower (r1, r5)
        for target in G.successors(local_borrower_name):
            ego_nodes.add(target)
            
        # 2. Incoming edges to borrower (r2, r4) and their properties
        for source in G.predecessors(local_borrower_name):
            ego_nodes.add(source)
            # 3. If source is a director (r2), we also want where they are director of (r3)
            # Cypher: MATCH (p:PERSON)-[r3:DIRECTOR_OF]->(related)
            for key, edge_data in G[source][local_borrower_name].items():
                if edge_data.get("type") == DIRECTOR_OF:
                    for related in G.successors(source):
                        ego_nodes.add(related)
                        
        # 4. Guarantors (r6) for LOAN nodes where borrower = borrower_name
        loan_id = f"loan-{local_borrower_name}"
        if G.has_node(loan_id):
            ego_nodes.add(loan_id)
            for source in G.predecessors(loan_id):
                for key, edge_data in G[source][loan_id].items():
                    if edge_data.get("type") == GUARANTOR_FOR:
                        ego_nodes.add(source)

        subgraph = G.subgraph(ego_nodes)
        
        for node, data in subgraph.nodes(data=True):
            node_id = str(node)
            props = dict(data)
            labels = props.pop("labels", [])
            node_type = _detect_node_type(labels)
            
            # The UI expects 'name' in properties sometimes, so ensure it's there
            name = props.get("name", props.get("job_id", props.get("borrower", node_id)))
            
            is_flagged = name in flagged_names
            flag_type = name_to_flag.get(name)
            
            nodes_by_id[node_id] = GraphNode(
                id=node_id,
                label=str(name),
                type=node_type,
                is_borrower=(str(name) == local_borrower_name),
                is_flagged=is_flagged,
                flag_type=flag_type,
                properties=_sanitize_props(props)
            )

        edge_counter = 0
        for u, v, key, data in subgraph.edges(keys=True, data=True):
            props = dict(data)
            rel_type = props.pop("type", "UNKNOWN")
            
            # Only export the specific edges from the Cypher query between these nodes
            if rel_type not in (DIRECTOR_OF, LENDER_TO, PAID_TO, SUBSIDIARY_OF, GUARANTOR_FOR, APPLIED_FOR, FLAGGED_IN):
                continue

            source_id = str(u)
            target_id = str(v)
            edge_id = f"edge-{source_id}-{target_id}-{rel_type}-{key}-{edge_counter}"
            edge_counter += 1
            
            source_name = str(subgraph.nodes[u].get("name", u))
            target_name = str(subgraph.nodes[v].get("name", v))
            is_flagged = source_name in flagged_names or target_name in flagged_names
            
            edges_by_id[edge_id] = GraphEdge(
                id=edge_id,
                source=source_id,
                target=target_id,
                type=rel_type,
                label=_edge_label(rel_type, props),
                is_flagged=is_flagged,
                properties=_sanitize_props(props)
            )
            
        return nodes_by_id, edges_by_id

    nodes_dict, edges_dict = await asyncio.to_thread(_extract_graph)
    
    export = GraphExport(
        job_id=job_id,
        nodes=list(nodes_dict.values()),
        edges=list(edges_dict.values()),
    )

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
    clean = {}
    for k, v in props.items():
        if k == "labels": continue
        if v is None:
            continue
        if isinstance(v, (str, int, float, bool)):
            clean[k] = v
        elif isinstance(v, list):
            clean[k] = v
        else:
            clean[k] = str(v)
    return clean

