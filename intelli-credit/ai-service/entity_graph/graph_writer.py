"""
Entity Graph Writer — writes EntityExtraction data into Neo4j.

Takes the EntityExtraction output from info_extractor.py and upserts all
entities and relationships into the Neo4j graph using MERGE.  Re-running
for the same company/job will not create duplicate nodes.

All writes execute in a SINGLE transaction — fully written or fully rolled back.
All Cypher uses $param syntax — never f-strings (prevents injection).
"""

import logging
from typing import Optional

from deep_learning.schemas import EntityExtraction
from .schemas import WriteResult
from .neo4j_client import (
    get_driver,
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
# Individual write functions (called inside a single transaction)
# =============================================================================

def write_application_node(tx, job_id: str, borrower_name: str) -> int:
    """MERGE the APPLICATION node for this job."""
    tx.run(
        f"MERGE (a:{APPLICATION} {{job_id: $job_id}}) "
        f"SET a.borrower_name = $borrower_name, a.created_at = datetime()",
        job_id=job_id,
        borrower_name=borrower_name,
    )
    return 1  # 1 node


def write_borrower_node(tx, company_name: str, cin: Optional[str]) -> int:
    """MERGE the borrower COMPANY node."""
    tx.run(
        f"MERGE (c:{COMPANY} {{name: $company_name}}) "
        f"SET c.cin = $cin, c.last_seen = datetime()",
        company_name=company_name,
        cin=cin,
    )
    return 1


def write_promoters(tx, promoters: list, company_name: str) -> tuple[int, int]:
    """MERGE PERSON nodes for each promoter and link to the company."""
    nodes = 0
    rels = 0
    for p in promoters:
        tx.run(
            f"MERGE (p:{PERSON} {{name: $name}}) "
            f"SET p.designation = $designation, p.din = $din",
            name=p.name,
            designation=p.designation,
            din=p.din,
        )
        nodes += 1

        tx.run(
            f"MERGE (p:{PERSON} {{name: $person_name}}) "
            f"MERGE (c:{COMPANY} {{name: $company_name}}) "
            f"MERGE (p)-[:{DIRECTOR_OF}]->(c)",
            person_name=p.name,
            company_name=company_name,
        )
        rels += 1

    return nodes, rels


def write_related_parties(
    tx, related_parties: list, borrower_name: str
) -> tuple[int, int]:
    """MERGE COMPANY nodes for related parties and link with PAID_TO."""
    nodes = 0
    rels = 0
    for rp in related_parties:
        tx.run(
            f"MERGE (rp:{COMPANY} {{name: $rp_name}}) "
            f"SET rp.flagged_as_related_party = true",
            rp_name=rp.name,
        )
        nodes += 1

        tx.run(
            f"MERGE (borrower:{COMPANY} {{name: $borrower_name}}) "
            f"MERGE (rp:{COMPANY} {{name: $rp_name}}) "
            f"MERGE (borrower)-[:{PAID_TO} {{"
            f"  amount_crore: $amount,"
            f"  relationship: $relationship,"
            f"  written_at: datetime()"
            f"}}]->(rp)",
            borrower_name=borrower_name,
            rp_name=rp.name,
            amount=rp.transaction_amount_crore or 0.0,
            relationship=rp.relationship or "unknown",
        )
        rels += 1

    return nodes, rels


def write_subsidiaries(
    tx, subsidiaries: list, borrower_name: str
) -> tuple[int, int]:
    """MERGE COMPANY nodes for subsidiaries and link with SUBSIDIARY_OF."""
    nodes = 0
    rels = 0
    for s in subsidiaries:
        tx.run(
            f"MERGE (s:{COMPANY} {{name: $sub_name}}) "
            f"SET s.cin = $cin",
            sub_name=s.name,
            cin=s.cin,
        )
        nodes += 1

        tx.run(
            f"MERGE (s:{COMPANY} {{name: $sub_name}}) "
            f"MERGE (parent:{COMPANY} {{name: $parent_name}}) "
            f"MERGE (s)-[:{SUBSIDIARY_OF}]->(parent)",
            sub_name=s.name,
            parent_name=borrower_name,
        )
        rels += 1

    return nodes, rels


def write_lenders(
    tx, lenders: list, borrower_name: str
) -> tuple[int, int]:
    """MERGE COMPANY nodes for banks and link with LENDER_TO."""
    nodes = 0
    rels = 0
    for l in lenders:
        tx.run(
            f"MERGE (bank:{COMPANY} {{name: $bank_name}}) "
            f"SET bank.is_bank = true",
            bank_name=l.bank_name,
        )
        nodes += 1

        tx.run(
            f"MERGE (bank:{COMPANY} {{name: $bank_name}}) "
            f"MERGE (borrower:{COMPANY} {{name: $borrower_name}}) "
            f"MERGE (bank)-[:{LENDER_TO} {{"
            f"  facility: $facility,"
            f"  amount_crore: $amount_crore"
            f"}}]->(borrower)",
            bank_name=l.bank_name,
            borrower_name=borrower_name,
            facility=l.facility_type or "unknown",
            amount_crore=l.amount_crore or 0.0,
        )
        rels += 1

    return nodes, rels


def write_guarantors(
    tx, guarantors: list, borrower_name: str
) -> tuple[int, int]:
    """MERGE PERSON nodes for guarantors and link with GUARANTOR_FOR via a LOAN node."""
    nodes = 0
    rels = 0
    for g in guarantors:
        tx.run(
            f"MERGE (g:{PERSON} {{name: $name}}) "
            f"SET g.relationship = $relationship",
            name=g.name,
            relationship=g.relationship_to_borrower,
        )
        nodes += 1

        # Create/find a LOAN node for this borrower
        tx.run(
            f"MERGE (borrower:{COMPANY} {{name: $borrower_name}}) "
            f"MERGE (loan:{LOAN} {{borrower: $borrower_name}}) "
            f"MERGE (g:{PERSON} {{name: $guarantor_name}}) "
            f"MERGE (g)-[:{GUARANTOR_FOR}]->(loan)",
            borrower_name=borrower_name,
            guarantor_name=g.name,
        )
        # LOAN node + relationship
        nodes += 1
        rels += 1

    return nodes, rels


def write_application_link(
    tx, borrower_name: str, job_id: str
) -> int:
    """Link the borrower COMPANY to the APPLICATION node."""
    tx.run(
        f"MERGE (c:{COMPANY} {{name: $borrower_name}}) "
        f"MERGE (a:{APPLICATION} {{job_id: $job_id}}) "
        f"MERGE (c)-[:{APPLIED_FOR}]->(a)",
        borrower_name=borrower_name,
        job_id=job_id,
    )
    return 1


# =============================================================================
# Orchestrator — runs everything in one transaction
# =============================================================================

def _execute_all_writes(
    tx,
    entity_data: EntityExtraction,
    job_id: str,
    borrower_name: str,
) -> tuple[int, int]:
    """
    Execute all graph writes in a single transaction.

    This function is passed to session.execute_write() so that
    Neo4j handles commit/rollback automatically.

    Returns:
        (total_nodes, total_relationships)
    """
    total_nodes = 0
    total_rels = 0

    # 1. Application node
    total_nodes += write_application_node(tx, job_id, borrower_name)

    # 2. Borrower company node
    total_nodes += write_borrower_node(
        tx, borrower_name, entity_data.cin
    )

    # 3. Promoters → DIRECTOR_OF
    if entity_data.promoters:
        n, r = write_promoters(tx, entity_data.promoters, borrower_name)
        total_nodes += n
        total_rels += r

    # 4. Related parties → PAID_TO
    if entity_data.related_parties:
        n, r = write_related_parties(
            tx, entity_data.related_parties, borrower_name
        )
        total_nodes += n
        total_rels += r

    # 5. Subsidiaries → SUBSIDIARY_OF
    if entity_data.subsidiaries:
        n, r = write_subsidiaries(
            tx, entity_data.subsidiaries, borrower_name
        )
        total_nodes += n
        total_rels += r

    # 6. Lenders → LENDER_TO
    if entity_data.existing_lenders:
        n, r = write_lenders(
            tx, entity_data.existing_lenders, borrower_name
        )
        total_nodes += n
        total_rels += r

    # 7. Guarantors → GUARANTOR_FOR
    if entity_data.guarantors:
        n, r = write_guarantors(
            tx, entity_data.guarantors, borrower_name
        )
        total_nodes += n
        total_rels += r

    # 8. Application link: COMPANY → APPLIED_FOR → APPLICATION
    total_rels += write_application_link(tx, borrower_name, job_id)

    return total_nodes, total_rels


async def write_entity_graph(
    entity_data: EntityExtraction,
    job_id: str,
) -> WriteResult:
    """
    Write all entities and relationships from EntityExtraction into Neo4j.

    Runs all writes in a single transaction — fully committed or fully
    rolled back.  Uses MERGE throughout so re-processing the same
    document will not create duplicate nodes.

    Args:
        entity_data: EntityExtraction from info_extractor.py.
        job_id:      Current loan application's job ID.

    Returns:
        WriteResult with counts and status.
    """
    import asyncio

    borrower_name = entity_data.company_name or f"Unknown-{job_id}"

    try:
        driver = get_driver()

        # Run the transactional write in a thread (Neo4j driver is sync)
        def _run_write():
            with driver.session() as session:
                return session.execute_write(
                    _execute_all_writes,
                    entity_data=entity_data,
                    job_id=job_id,
                    borrower_name=borrower_name,
                )

        total_nodes, total_rels = await asyncio.to_thread(_run_write)

        logger.info(
            f"[{job_id}] Graph write complete: "
            f"{total_nodes} nodes, {total_rels} relationships "
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
        return WriteResult(
            job_id=job_id,
            nodes_written=0,
            relationships_written=0,
            status="failed",
            error=str(e),
        )
