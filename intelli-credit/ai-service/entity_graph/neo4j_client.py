"""
Neo4j connection client and schema definitions for the Entity Graph module.

=============================================================================
Neo4j runs as a Docker container alongside ai-service.
  - Docker:    bolt://neo4j:7687
  - Local dev: bolt://localhost:7687

Connection is a module-level singleton — one driver for the entire service.
Constraints are applied once at startup via create_constraints().
=============================================================================
"""

import logging
import os
from typing import Optional

from neo4j import GraphDatabase, Driver

logger = logging.getLogger("entity_graph.neo4j_client")


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

_driver: Optional[Driver] = None


def get_driver() -> Driver:
    """
    Return the module-level Neo4j driver singleton.

    Creates the driver on first call using environment variables:
      - NEO4J_URI      (default: bolt://neo4j:7687)
      - NEO4J_USER     (default: neo4j)
      - NEO4J_PASSWORD (required)

    Raises:
        KeyError: If NEO4J_PASSWORD is not set.
    """
    global _driver
    if _driver is None:
        uri = os.environ.get("NEO4J_URI", "bolt://neo4j:7687")
        user = os.environ.get("NEO4J_USER", "neo4j")
        password = os.environ["NEO4J_PASSWORD"]
        _driver = GraphDatabase.driver(uri, auth=(user, password))
        logger.info(f"Neo4j driver created: {uri} (user={user})")
    return _driver


def close_driver() -> None:
    """Close the Neo4j driver and release the singleton."""
    global _driver
    if _driver is not None:
        _driver.close()
        _driver = None
        logger.info("Neo4j driver closed")


# =============================================================================
# CONSTRAINTS (run once at startup)
# =============================================================================

_CONSTRAINT_QUERIES = [
    f"CREATE CONSTRAINT IF NOT EXISTS FOR (p:{PERSON}) REQUIRE p.name IS UNIQUE",
    f"CREATE CONSTRAINT IF NOT EXISTS FOR (c:{COMPANY}) REQUIRE c.name IS UNIQUE",
    f"CREATE CONSTRAINT IF NOT EXISTS FOR (a:{APPLICATION}) REQUIRE a.job_id IS UNIQUE",
]


def create_constraints(driver: Optional[Driver] = None) -> None:
    """
    Create uniqueness constraints on the Neo4j graph.

    Safe to call multiple times — uses CREATE CONSTRAINT IF NOT EXISTS.
    Should be called once at FastAPI startup (lifespan).

    Args:
        driver: Neo4j driver instance. If None, uses the singleton.
    """
    drv = driver or get_driver()
    with drv.session() as session:
        for query in _CONSTRAINT_QUERIES:
            session.run(query)
            logger.debug(f"Constraint applied: {query}")
    logger.info(f"Neo4j constraints applied ({len(_CONSTRAINT_QUERIES)} total)")


# =============================================================================
# HEALTH CHECK
# =============================================================================

def neo4j_health_check() -> bool:
    """
    Check Neo4j connectivity by running a trivial query.

    Returns:
        True if Neo4j is reachable and responding, False otherwise.
    """
    try:
        driver = get_driver()
        with driver.session() as session:
            session.run("RETURN 1").consume()
        return True
    except Exception as e:
        logger.warning(f"Neo4j health check failed: {e}")
        return False
