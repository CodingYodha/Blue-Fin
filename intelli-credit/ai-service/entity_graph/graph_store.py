"""
Graph connection client and schema definitions for the Entity Graph module.
Uses NetworkX as an in-memory database with persistence to Pickle.
"""

import logging
import os
import pickle
import threading
from pathlib import Path
from typing import Optional

import networkx as nx

logger = logging.getLogger("entity_graph.graph_store")


# =============================================================================
# NODE LABELS
# =============================================================================

PERSON = "PERSON"           # A human: promoter, director, guarantor
COMPANY = "COMPANY"         # Any legal entity: borrower, supplier, subsidiary
LOAN = "LOAN"               # An existing credit facility
APPLICATION = "APPLICATION"  # A loan application processed by Intelli-Credit


# =============================================================================
# RELATIONSHIP TYPES
# =============================================================================

DIRECTOR_OF = "DIRECTOR_OF"         # (Person)-[:DIRECTOR_OF]->(Company)
GUARANTOR_FOR = "GUARANTOR_FOR"     # (Person)-[:GUARANTOR_FOR]->(Loan)
SUPPLIER_TO = "SUPPLIER_TO"         # (Company)-[:SUPPLIER_TO {amount_crore, year}]->(Company)
SUBSIDIARY_OF = "SUBSIDIARY_OF"     # (Company)-[:SUBSIDIARY_OF]->(Company)
LENDER_TO = "LENDER_TO"             # (Company)-[:LENDER_TO {facility, amount_crore}]->(Company)
PAID_TO = "PAID_TO"                 # (Company)-[:PAID_TO {amount_crore, description}]->(Company)
APPLIED_FOR = "APPLIED_FOR"         # (Company)-[:APPLIED_FOR]->(Application)
FLAGGED_IN = "FLAGGED_IN"           # (Company|Person)-[:FLAGGED_IN {reason}]->(Application)


# =============================================================================
# CONNECTION SINGLETON
# =============================================================================

_graph: Optional[nx.MultiDiGraph] = None
_lock = threading.Lock()
_PERSIST_PATH = Path("/tmp/intelli-credit/global_graph.pkl")

def get_graph() -> nx.MultiDiGraph:
    """
    Return the module-level NetworkX graph singleton.
    """
    global _graph
    with _lock:
        if _graph is None:
            if _PERSIST_PATH.exists():
                try:
                    with open(_PERSIST_PATH, "rb") as f:
                        _graph = pickle.load(f)
                    logger.info(f"[Graph] Loaded graph from {_PERSIST_PATH} ({_graph.number_of_nodes()} nodes)")
                except Exception as e:
                    logger.error(f"[Graph] Failed to load graph: {e}")
                    _graph = nx.MultiDiGraph()
            else:
                _graph = nx.MultiDiGraph()
                _PERSIST_PATH.parent.mkdir(parents=True, exist_ok=True)
                logger.info(f"[Graph] Created new empty graph")
        return _graph

def save_graph() -> None:
    """
    Persist the in-memory graph to disk.
    """
    global _graph
    with _lock:
        if _graph is not None:
            try:
                _PERSIST_PATH.parent.mkdir(parents=True, exist_ok=True)
                with open(_PERSIST_PATH, "wb") as f:
                    pickle.dump(_graph, f)
                logger.debug(f"[Graph] Saved graph to {_PERSIST_PATH}")
            except Exception as e:
                logger.error(f"[Graph] Failed to save graph: {e}")

# Maintain original function names for backward compatibility if needed, but 
# clients should migrate to get_graph() and save_graph().
def get_driver() -> str:
    # Dummy string to pass "if driver is None:" checks
    return "networkx"

def close_driver() -> None:
    save_graph()
    logger.info("Graph saved on close")

def create_constraints(driver: Optional[str] = None) -> None:
    pass

def neo4j_health_check() -> bool:
    return True
