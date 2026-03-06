"""
Fuzzy Entity Matcher — links NER entity names to bank transaction descriptions.

=============================================================================
V12 FIX: Related-party fund siphoning detection
=============================================================================
Problem:
  NER extracts 'Alpha Trading Co.' from an Annual Report.
  Bank statement has a transaction to 'NEFT/ALPHA-TRDG-PVT'.
  Strict string matching finds zero connections.
  The related-party fund siphoning of ₹4.2 Crore goes undetected.

Fix:
  Fuzzy matching via thefuzz.fuzz.token_sort_ratio() links entity names
  to transaction descriptions.  token_sort_ratio is order-insensitive
  and handles partial abbreviations.

Thresholds:
  ≥85 → CONFIRMED_MATCH  (auto-linked in graph)
  70-84 → PROBABLE_MATCH  (linked with lower confidence, flagged for review)
  <70 → NO_MATCH
=============================================================================
"""

import logging
import re
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field
from thefuzz import fuzz

logger = logging.getLogger("entity_graph.fuzzy_matcher")


# =============================================================================
# Models
# =============================================================================

class MatchConfidence(str, Enum):
    """Match confidence level based on fuzzy score."""
    CONFIRMED_MATCH = "CONFIRMED_MATCH"   # score >= 85
    PROBABLE_MATCH = "PROBABLE_MATCH"     # 70 <= score < 85
    NO_MATCH = "NO_MATCH"                 # score < 70


class EntityMatchResult(BaseModel):
    """A single fuzzy match result between an entity and a transaction."""

    model_config = {"json_schema_extra": {"title": "EntityMatchResult"}}

    entity_name: str = Field(
        ..., description="Original NER entity name"
    )
    matched_description: str = Field(
        ..., description="Bank transaction description that matched"
    )
    score: int = Field(
        ..., description="Fuzzy match score (0-100)"
    )
    confidence: MatchConfidence = Field(
        ..., description="CONFIRMED_MATCH, PROBABLE_MATCH, or NO_MATCH"
    )


class TransactionLinkResult(BaseModel):
    """Summary of fuzzy-match linking across all entities and transactions."""

    model_config = {"json_schema_extra": {"title": "TransactionLinkResult"}}

    confirmed_links: int = Field(
        default=0, description="Number of CONFIRMED_MATCH relationships written"
    )
    probable_links: int = Field(
        default=0, description="Number of PROBABLE_MATCH relationships written"
    )
    entities_checked: int = Field(
        default=0, description="Total NER entity names checked"
    )
    transactions_checked: int = Field(
        default=0, description="Total transaction descriptions checked"
    )


# =============================================================================
# Suffixes and prefixes to strip during normalization
# =============================================================================

_CORPORATE_SUFFIXES = {
    "PVT", "LTD", "LIMITED", "PRIVATE", "CO", "CORP",
    "INC", "LLP", "PLC", "COMPANY",
}

_TRANSACTION_PREFIXES = re.compile(
    r"^(NEFT|RTGS|IMPS|UPI|ACH|ECS)[/\\-]",
    re.IGNORECASE,
)

_SPECIAL_CHARS = re.compile(r"[/\-_.\\\,\(\)\[\]]")


# =============================================================================
# Functions
# =============================================================================

def normalize_entity_name(name: str) -> str:
    """
    Pre-process an entity or transaction name for fuzzy comparison.

    Steps:
      1. Uppercase
      2. Remove NEFT/RTGS/IMPS/UPI/ACH/ECS prefixes
      3. Remove special characters: / - _ . \\ , ( ) [ ]
      4. Remove common corporate suffixes: PVT, LTD, LIMITED, etc.
      5. Collapse multiple spaces

    Examples:
      "NEFT/ALPHA-TRDG-PVT LTD" → "ALPHA TRDG"
      "Alpha Trading Co."        → "ALPHA TRADING"
    """
    result = name.upper().strip()

    # Remove transaction prefixes
    result = _TRANSACTION_PREFIXES.sub("", result)

    # Remove special characters
    result = _SPECIAL_CHARS.sub(" ", result)

    # Remove corporate suffixes (word-boundary aware)
    words = result.split()
    words = [w for w in words if w not in _CORPORATE_SUFFIXES]

    # Rejoin and collapse whitespace
    result = " ".join(words).strip()

    return result


def match_score(name_a: str, name_b: str) -> int:
    """
    Compute fuzzy match score between two entity/transaction names.

    Normalizes both names first, then uses token_sort_ratio which:
      - Sorts tokens alphabetically before comparison
      - Handles word reordering ('Alpha Trading' vs 'Trading Alpha')
      - Works well with partial abbreviations

    Args:
        name_a: First name (e.g. NER entity name).
        name_b: Second name (e.g. bank transaction description).

    Returns:
        Score 0-100 (higher = more similar).
    """
    norm_a = normalize_entity_name(name_a)
    norm_b = normalize_entity_name(name_b)

    if not norm_a or not norm_b:
        return 0

    return fuzz.token_sort_ratio(norm_a, norm_b)


def classify_match(score: int) -> MatchConfidence:
    """
    Classify a fuzzy match score into a confidence level.

    Args:
        score: Fuzzy match score (0-100).

    Returns:
        CONFIRMED_MATCH (≥85), PROBABLE_MATCH (70-84), or NO_MATCH (<70).
    """
    if score >= 85:
        return MatchConfidence.CONFIRMED_MATCH
    elif score >= 70:
        return MatchConfidence.PROBABLE_MATCH
    else:
        return MatchConfidence.NO_MATCH


def find_entity_in_transactions(
    entity_name: str,
    transaction_descriptions: List[str],
) -> List[EntityMatchResult]:
    """
    Find fuzzy matches for a single entity name across all transaction descriptions.

    Args:
        entity_name:              NER entity name to search for.
        transaction_descriptions: List of bank transaction descriptions.

    Returns:
        List of EntityMatchResult for CONFIRMED and PROBABLE matches,
        sorted by score descending.
    """
    results: List[EntityMatchResult] = []

    for desc in transaction_descriptions:
        score = match_score(entity_name, desc)
        confidence = classify_match(score)

        if confidence != MatchConfidence.NO_MATCH:
            results.append(
                EntityMatchResult(
                    entity_name=entity_name,
                    matched_description=desc,
                    score=score,
                    confidence=confidence,
                )
            )

    # Sort by score descending
    results.sort(key=lambda r: r.score, reverse=True)

    if results:
        logger.info(
            f"Entity '{entity_name}': {len(results)} matches "
            f"(best={results[0].score}, confidence={results[0].confidence.value})"
        )

    return results


async def link_transactions_to_graph(
    entity_extractions: List[str],
    transaction_descriptions: List[str],
    job_id: str,
    driver,
) -> TransactionLinkResult:
    """
    Fuzzy-match NER entity names to bank transactions and write
    PAID_TO relationships into Neo4j.

    For CONFIRMED matches: writes PAID_TO with confidence="CONFIRMED".
    For PROBABLE matches: writes PAID_TO with confidence="PROBABLE"
    (displayed differently in the frontend for human review).

    Args:
        entity_extractions:       List of NER entity names.
        transaction_descriptions: List of bank transaction descriptions.
        job_id:                   Current job ID (for logging).
        driver:                   Neo4j driver instance.

    Returns:
        TransactionLinkResult with counts of links created.
    """
    import asyncio
    from .neo4j_client import COMPANY, PAID_TO

    confirmed_links = 0
    probable_links = 0

    def _write_links():
        nonlocal confirmed_links, probable_links

        with driver.session() as session:
            for entity_name in entity_extractions:
                matches = find_entity_in_transactions(
                    entity_name, transaction_descriptions
                )

                for match in matches:
                    confidence_str = match.confidence.value

                    session.run(
                        f"MERGE (src:{COMPANY} {{name: $entity_name}}) "
                        f"MERGE (dst:{COMPANY} {{name: $matched_name}}) "
                        f"MERGE (src)-[r:{PAID_TO}]->(dst) "
                        f"SET r.confidence = $confidence, "
                        f"    r.matched_via = 'fuzzy', "
                        f"    r.fuzzy_score = $score, "
                        f"    r.raw_description = $raw_desc, "
                        f"    r.job_id = $job_id, "
                        f"    r.written_at = datetime()",
                        entity_name=entity_name,
                        matched_name=match.matched_description,
                        confidence=confidence_str,
                        score=match.score,
                        raw_desc=match.matched_description,
                        job_id=job_id,
                    )

                    if match.confidence == MatchConfidence.CONFIRMED_MATCH:
                        confirmed_links += 1
                    else:
                        probable_links += 1

    await asyncio.to_thread(_write_links)

    logger.info(
        f"[{job_id}] Transaction linking complete: "
        f"{confirmed_links} confirmed, {probable_links} probable "
        f"({len(entity_extractions)} entities × "
        f"{len(transaction_descriptions)} transactions)"
    )

    return TransactionLinkResult(
        confirmed_links=confirmed_links,
        probable_links=probable_links,
        entities_checked=len(entity_extractions),
        transactions_checked=len(transaction_descriptions),
    )
