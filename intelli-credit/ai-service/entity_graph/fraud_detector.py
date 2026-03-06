"""
Fraud Detector — Cypher read queries against Neo4j for fraud pattern detection.

=============================================================================
Runs AFTER graph_writer.py has written all entities for the current application.
The graph contains entities from the CURRENT application AND all HISTORICAL
applications — enabling cross-application fraud detection (the core value of
replacing NetworkX with Neo4j).

Detected patterns:
  1. Related-party director overlap (CRITICAL)
  2. Historical rejection match (HIGH)
  3. Shell supplier network (HIGH)
  4. Circular ownership payment (HIGH)

Output:
  FraudDetectionResult → written to /tmp/intelli-credit/{job_id}/entity_fraud_flags.json
  (V11 pattern — downstream ML service reads this file, not an HTTP call)
=============================================================================
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .schemas import FraudFlag, FraudDetectionResult
from .neo4j_client import (
    COMPANY,
    PERSON,
    APPLICATION,
    PAID_TO,
    DIRECTOR_OF,
    SUBSIDIARY_OF,
    APPLIED_FOR,
)

logger = logging.getLogger("entity_graph.fraud_detector")

# Shared volume base path
_BASE_PATH = Path("/tmp/intelli-credit")


# =============================================================================
# Severity ranking for comparison
# =============================================================================

_SEVERITY_RANK = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1, "NONE": 0}


def _highest_severity(flags: List[FraudFlag]) -> str:
    """Return the highest severity across all flags."""
    if not flags:
        return "NONE"
    return max(flags, key=lambda f: _SEVERITY_RANK.get(f.severity, 0)).severity


# =============================================================================
# Fraud Detection Functions
# =============================================================================

def detect_related_party_director_overlap(
    driver, job_id: str, borrower_name: str
) -> Optional[FraudFlag]:
    """
    Detect: A supplier of the borrower shares a director with the borrower.
    Classic related-party siphoning pattern.
    """
    query = (
        f"MATCH (borrower:{COMPANY} {{name: $borrower_name}})"
        f"-[:{PAID_TO}]->(supplier:{COMPANY}) "
        f"MATCH (supplier)<-[:{DIRECTOR_OF}]-(shared_director:{PERSON}) "
        f"MATCH (shared_director)-[:{DIRECTOR_OF}]->(borrower) "
        f"RETURN shared_director.name AS director, "
        f"       supplier.name AS supplier, "
        f"       supplier.transaction_amount_crore AS amount"
    )

    with driver.session() as session:
        result = session.run(query, borrower_name=borrower_name)
        record = result.single()

    if record is None:
        return None

    director = record["director"]
    supplier = record["supplier"]
    amount = record["amount"] or 0

    logger.warning(
        f"[{job_id}] FRAUD: Director overlap — {director} is director of "
        f"both {borrower_name} and supplier {supplier}"
    )

    return FraudFlag(
        flag_type="RELATED_PARTY_DIRECTOR_OVERLAP",
        severity="CRITICAL",
        score_penalty=-25,
        description=(
            f"{director} is director of both {borrower_name} and its "
            f"supplier {supplier}. Payment: ₹{amount}Cr"
        ),
        evidence={
            "director": director,
            "supplier": supplier,
            "amount_crore": amount,
        },
        source="Entity Graph — Neo4j Cypher traversal",
    )


def detect_historical_rejection(
    driver, job_id: str, borrower_name: str
) -> Optional[FraudFlag]:
    """
    Detect: The same company or a company sharing a director has been
    rejected in a previous Intelli-Credit application.
    """
    # Direct rejection
    direct_query = (
        f"MATCH (borrower:{COMPANY} {{name: $borrower_name}})"
        f"-[:{APPLIED_FOR}]->(prev_app:{APPLICATION}) "
        f"WHERE prev_app.job_id <> $job_id AND prev_app.decision = 'REJECT' "
        f"RETURN prev_app.job_id AS prev_job, "
        f"       prev_app.borrower_name AS prev_company"
    )

    with driver.session() as session:
        result = session.run(
            direct_query, borrower_name=borrower_name, job_id=job_id
        )
        direct_record = result.single()

    if direct_record is not None:
        prev_job = direct_record["prev_job"]
        logger.warning(
            f"[{job_id}] FRAUD: Direct historical rejection — "
            f"{borrower_name} was rejected in {prev_job}"
        )
        return FraudFlag(
            flag_type="HISTORICAL_REJECTION_MATCH",
            severity="HIGH",
            score_penalty=-15,
            description=(
                f"{borrower_name} was previously rejected in "
                f"application {prev_job}"
            ),
            evidence={
                "previous_job_id": prev_job,
                "previous_company": direct_record["prev_company"],
                "match_type": "direct",
            },
            source="Entity Graph — cross-application historical query",
        )

    # Director-linked rejection
    linked_query = (
        f"MATCH (borrower:{COMPANY} {{name: $borrower_name}})"
        f"<-[:{DIRECTOR_OF}]-(d:{PERSON}) "
        f"MATCH (d)-[:{DIRECTOR_OF}]->(other:{COMPANY})"
        f"-[:{APPLIED_FOR}]->(prev:{APPLICATION}) "
        f"WHERE prev.decision = 'REJECT' "
        f"RETURN d.name AS shared_director, "
        f"       other.name AS rejected_company, "
        f"       prev.job_id AS prev_job"
    )

    with driver.session() as session:
        result = session.run(
            linked_query, borrower_name=borrower_name
        )
        linked_record = result.single()

    if linked_record is not None:
        director = linked_record["shared_director"]
        rejected = linked_record["rejected_company"]
        prev_job = linked_record["prev_job"]

        logger.warning(
            f"[{job_id}] FRAUD: Director-linked rejection — "
            f"{director} linked to rejected {rejected} ({prev_job})"
        )
        return FraudFlag(
            flag_type="HISTORICAL_REJECTION_MATCH",
            severity="HIGH",
            score_penalty=-15,
            description=(
                f"Director {director} linked to previously rejected "
                f"application {prev_job} ({rejected})"
            ),
            evidence={
                "shared_director": director,
                "rejected_company": rejected,
                "previous_job_id": prev_job,
                "match_type": "director_linked",
            },
            source="Entity Graph — cross-application historical query",
        )

    return None


def detect_shell_supplier_network(
    driver, job_id: str, borrower_name: str
) -> Optional[FraudFlag]:
    """
    Detect: Multiple suppliers of the borrower share the same director —
    suggesting a shell company network controlled by the promoter.
    """
    query = (
        f"MATCH (borrower:{COMPANY} {{name: $borrower_name}})"
        f"-[:{PAID_TO}]->(supplier:{COMPANY}) "
        f"MATCH (supplier)<-[:{DIRECTOR_OF}]-(d:{PERSON}) "
        f"WITH d, COLLECT(supplier.name) AS controlled_suppliers "
        f"WHERE SIZE(controlled_suppliers) >= 2 "
        f"RETURN d.name AS controller, controlled_suppliers"
    )

    with driver.session() as session:
        result = session.run(query, borrower_name=borrower_name)
        record = result.single()

    if record is None:
        return None

    controller = record["controller"]
    suppliers = record["controlled_suppliers"]

    logger.warning(
        f"[{job_id}] FRAUD: Shell network — {controller} controls "
        f"{len(suppliers)} suppliers: {suppliers}"
    )

    return FraudFlag(
        flag_type="SHELL_SUPPLIER_NETWORK",
        severity="HIGH",
        score_penalty=-20,
        description=(
            f"{controller} controls {len(suppliers)} suppliers of "
            f"the borrower: {', '.join(suppliers)}"
        ),
        evidence={
            "controller": controller,
            "suppliers": suppliers,
        },
        source="Entity Graph — shell network Cypher",
    )


def detect_circular_ownership(
    driver, job_id: str, borrower_name: str
) -> Optional[FraudFlag]:
    """
    Detect: A subsidiary of the borrower is also a supplier to the borrower —
    money flowing in a circle within the group.
    """
    query = (
        f"MATCH (borrower:{COMPANY} {{name: $borrower_name}})"
        f"<-[:{SUBSIDIARY_OF}]-(sub:{COMPANY}) "
        f"MATCH (borrower)-[:{PAID_TO}]->(sub) "
        f"RETURN sub.name AS circular_entity"
    )

    with driver.session() as session:
        result = session.run(query, borrower_name=borrower_name)
        record = result.single()

    if record is None:
        return None

    entity = record["circular_entity"]

    logger.warning(
        f"[{job_id}] FRAUD: Circular ownership — {entity} is both "
        f"subsidiary and supplier of {borrower_name}"
    )

    return FraudFlag(
        flag_type="CIRCULAR_OWNERSHIP_PAYMENT",
        severity="HIGH",
        score_penalty=-20,
        description=(
            f"{entity} is both a subsidiary of and a paid supplier "
            f"to the borrower"
        ),
        evidence={
            "circular_entity": entity,
            "borrower": borrower_name,
        },
        source="Entity Graph — circular ownership Cypher",
    )


# =============================================================================
# Orchestrator
# =============================================================================

async def run_all_fraud_checks(
    driver, job_id: str, borrower_name: str
) -> FraudDetectionResult:
    """
    Run all 4 fraud detection checks and write results to disk.

    Executes each check independently — one failure does not block others.
    Writes FraudDetectionResult to:
      /tmp/intelli-credit/{job_id}/entity_fraud_flags.json

    Args:
        driver:        Neo4j driver instance.
        job_id:        Current loan application job ID.
        borrower_name: Primary borrower company name.

    Returns:
        FraudDetectionResult with all flags and aggregate scores.
    """
    import asyncio

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
                flag = check_fn(driver, job_id, borrower_name)
                if flag is not None:
                    flags.append(flag)
            except Exception as e:
                logger.error(
                    f"[{job_id}] Fraud check '{check_name}' failed: {e}"
                )

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

    # Write to disk (V11 filesystem handoff)
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
