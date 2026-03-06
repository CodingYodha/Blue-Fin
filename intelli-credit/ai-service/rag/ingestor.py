"""
RAG Ingestor — reads Go service chunks, embeds via Jina, stores in Qdrant.

=============================================================================
Data flow:
  Go service → /tmp/intelli-credit/{job_id}/chunks.json
  This module reads that file, assigns embed_priority, calls Jina API for
  embeddings, and upserts vectors into Qdrant with rich metadata.

  Go owns chunking — this module does NOT re-chunk.

Embed priority rules:
  annual_report, rating_report → HIGH base
  legal_notice                 → MEDIUM base
  gst_filing                   → LOW base
  Section-name keywords can upgrade any chunk to HIGH.

Idempotency:
  Uses uuid5(NAMESPACE_URL, "{job_id}:{doc_type}:{chunk_index}") for each point.
  Qdrant upsert overwrites existing vectors — safe to re-run.
=============================================================================
"""

import json
import logging
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field
from qdrant_client.models import PointStruct, FilterSelector, Filter, FieldCondition, MatchValue

from .qdrant_client import get_client, COLLECTION_NAME
from .embedder import embed_chunks_batched, ChunkInput

logger = logging.getLogger("rag.ingestor")

# Shared volume base path
_BASE_PATH = Path("/tmp/intelli-credit")

# Qdrant upsert batch size
QDRANT_UPSERT_BATCH = 100


# =============================================================================
# IngestResult schema
# =============================================================================

class IngestResult(BaseModel):
    """Result of ingesting chunks for a single doc_type."""

    model_config = ConfigDict(from_attributes=True)

    job_id: str = Field(..., description="Job ID")
    doc_type: str = Field(..., description="Document type processed")
    chunks_read: int = Field(default=0, description="Chunks read from chunks.json")
    chunks_embedded: int = Field(default=0, description="Chunks successfully embedded")
    chunks_stored: int = Field(default=0, description="Chunks stored in Qdrant")
    high_priority_count: int = Field(default=0, description="Chunks with HIGH priority")
    medium_priority_count: int = Field(default=0, description="Chunks with MEDIUM priority")
    low_priority_count: int = Field(default=0, description="Chunks with LOW priority")
    status: str = Field(
        default="success",
        description="'success', 'skipped', 'partial', or 'failed'",
    )
    error: Optional[str] = Field(
        default=None, description="Error message if status is 'failed'"
    )


# =============================================================================
# Embed priority assignment
# =============================================================================

HIGH_PRIORITY_SECTIONS = [
    "Management Discussion", "Balance Sheet", "Profit and Loss",
    "Notes to Accounts", "Contingent Liabilities", "Related Party",
    "Auditor Report", "Debt Schedule", "Financial Highlights",
    "Rating Rationale", "Outlook", "Key Rating Drivers",
    "Covenant Terms", "Collateral", "Sanction Conditions",
]


def assign_embed_priority(doc_type: str, section_name: str) -> str:
    """
    Assign embedding priority based on doc_type and section_name.

    Rules:
      - annual_report, rating_report → HIGH base
      - legal_notice → MEDIUM base
      - gst_filing → LOW base
      - Section name keywords can upgrade any chunk to HIGH

    Args:
        doc_type:     Document type string.
        section_name: Section name from the chunker.

    Returns:
        "HIGH", "MEDIUM", or "LOW"
    """
    if doc_type in ("annual_report", "rating_report"):
        base = "HIGH"
    elif doc_type == "legal_notice":
        base = "MEDIUM"
    elif doc_type == "gst_filing":
        base = "LOW"
    else:
        base = "MEDIUM"

    # Upgrade to HIGH if section matches regardless of doc_type
    section_lower = section_name.lower()
    for keyword in HIGH_PRIORITY_SECTIONS:
        if keyword.lower() in section_lower:
            return "HIGH"

    return base


# =============================================================================
# Deterministic UUID for idempotent upsert
# =============================================================================

def _chunk_uuid(job_id: str, doc_type: str, chunk_index: int) -> str:
    """
    Generate a deterministic UUID for a chunk.

    Uses uuid5(NAMESPACE_URL, "{job_id}:{doc_type}:{chunk_index}")
    so the same chunk always gets the same UUID — upsert is safe.
    """
    key = f"{job_id}:{doc_type}:{chunk_index}"
    return str(uuid.uuid5(uuid.NAMESPACE_URL, key))


# =============================================================================
# Core ingest function
# =============================================================================

async def ingest_chunks_for_job(
    job_id: str,
    company_name: str,
    doc_type: str,
) -> IngestResult:
    """
    Read chunks from Go service, embed via Jina, store in Qdrant.

    Steps:
      1. Read /tmp/intelli-credit/{job_id}/chunks.json
      2. Filter chunks by doc_type
      3. Assign embed_priority
      4. Embed via Jina (batches of 32)
      5. Upsert into Qdrant (batches of 100)

    Args:
        job_id:       Loan application job ID.
        company_name: Borrower company name.
        doc_type:     Document type to filter for.

    Returns:
        IngestResult with counts and status.
    """
    chunks_file = _BASE_PATH / job_id / "chunks.json"

    # Step 1: Read chunks.json
    if not chunks_file.exists():
        logger.warning(
            f"[{job_id}] chunks.json not found at {chunks_file} — skipping ingest"
        )
        return IngestResult(
            job_id=job_id,
            doc_type=doc_type,
            status="skipped",
            error="chunks.json not found",
        )

    try:
        raw = json.loads(chunks_file.read_text(encoding="utf-8"))
    except Exception as e:
        logger.error(f"[{job_id}] Failed to parse chunks.json: {e}")
        return IngestResult(
            job_id=job_id,
            doc_type=doc_type,
            status="failed",
            error=f"Failed to parse chunks.json: {e}",
        )

    # Step 2: Filter by doc_type
    filtered = [c for c in raw if c.get("doc_type") == doc_type]
    if not filtered:
        logger.info(
            f"[{job_id}] No chunks for doc_type='{doc_type}' in chunks.json — skipping"
        )
        return IngestResult(
            job_id=job_id,
            doc_type=doc_type,
            chunks_read=0,
            status="skipped",
            error=f"No chunks for doc_type '{doc_type}'",
        )

    chunks_read = len(filtered)
    logger.info(f"[{job_id}] Read {chunks_read} chunks for doc_type='{doc_type}'")

    # Step 3: Assign embed_priority and build ChunkInput list
    high_count = 0
    medium_count = 0
    low_count = 0
    chunk_inputs: List[ChunkInput] = []

    for chunk in filtered:
        section_name = chunk.get("section_name", "")
        priority = assign_embed_priority(doc_type, section_name)

        if priority == "HIGH":
            high_count += 1
        elif priority == "MEDIUM":
            medium_count += 1
        else:
            low_count += 1

        chunk_inputs.append(
            ChunkInput(
                chunk_text=chunk["chunk_text"],
                metadata={
                    "job_id": job_id,
                    "company_name": company_name,
                    "doc_type": doc_type,
                    "page_num": chunk.get("page_num", 0),
                    "section_name": section_name,
                    "chunk_index": chunk.get("chunk_index", 0),
                    "embed_priority": priority,
                    "char_count": len(chunk["chunk_text"]),
                    "source_file": chunk.get("source_file", ""),
                },
            )
        )

    # Step 4: Embed via Jina
    try:
        embedded = await embed_chunks_batched(chunk_inputs)
        chunks_embedded = len(embedded)
        logger.info(
            f"[{job_id}] Embedded {chunks_embedded}/{chunks_read} chunks "
            f"(HIGH={high_count}, MEDIUM={medium_count}, LOW={low_count})"
        )
    except Exception as e:
        logger.error(f"[{job_id}] Embedding failed for doc_type='{doc_type}': {e}")
        return IngestResult(
            job_id=job_id,
            doc_type=doc_type,
            chunks_read=chunks_read,
            chunks_embedded=0,
            high_priority_count=high_count,
            medium_priority_count=medium_count,
            low_priority_count=low_count,
            status="failed",
            error=f"Embedding failed: {e}",
        )

    # Step 5: Build Qdrant PointStruct list and upsert
    points: List[PointStruct] = []
    for emb in embedded:
        chunk_index = emb.metadata.get("chunk_index", 0)
        point_id = _chunk_uuid(job_id, doc_type, chunk_index)

        payload = {
            **emb.metadata,
            "chunk_text": emb.chunk_text,
        }

        points.append(
            PointStruct(
                id=point_id,
                vector=emb.vector,
                payload=payload,
            )
        )

    # Upsert in batches of 100
    client = get_client()
    chunks_stored = 0

    try:
        for i in range(0, len(points), QDRANT_UPSERT_BATCH):
            batch = points[i : i + QDRANT_UPSERT_BATCH]
            client.upsert(
                collection_name=COLLECTION_NAME,
                points=batch,
            )
            chunks_stored += len(batch)
            logger.info(
                f"[{job_id}] Upserted batch {i // QDRANT_UPSERT_BATCH + 1} "
                f"({len(batch)} points, total={chunks_stored})"
            )
    except Exception as e:
        logger.error(f"[{job_id}] Qdrant upsert failed: {e}")
        return IngestResult(
            job_id=job_id,
            doc_type=doc_type,
            chunks_read=chunks_read,
            chunks_embedded=chunks_embedded,
            chunks_stored=chunks_stored,
            high_priority_count=high_count,
            medium_priority_count=medium_count,
            low_priority_count=low_count,
            status="partial" if chunks_stored > 0 else "failed",
            error=f"Qdrant upsert failed: {e}",
        )

    logger.info(
        f"[{job_id}] ✅ Ingest complete for '{doc_type}': "
        f"{chunks_stored} vectors stored in Qdrant"
    )

    return IngestResult(
        job_id=job_id,
        doc_type=doc_type,
        chunks_read=chunks_read,
        chunks_embedded=chunks_embedded,
        chunks_stored=chunks_stored,
        high_priority_count=high_count,
        medium_priority_count=medium_count,
        low_priority_count=low_count,
        status="success",
    )


# =============================================================================
# Multi-doc ingest orchestrator
# =============================================================================

# Priority order — bank_statement intentionally excluded (never embedded)
_DOC_TYPE_ORDER = [
    "annual_report",
    "rating_report",
    "legal_notice",
    "gst_filing",
]


async def ingest_all_documents(
    job_id: str,
    company_name: str,
    doc_types: List[str],
) -> List[IngestResult]:
    """
    Ingest chunks for multiple doc_types in priority order.

    Runs sequentially (not concurrently) to avoid overwhelming Jina API
    rate limits. bank_statement is intentionally excluded.

    Args:
        job_id:       Loan application job ID.
        company_name: Borrower company name.
        doc_types:    List of doc_types to ingest.

    Returns:
        List of IngestResult, one per doc_type attempted.
    """
    # Filter and order by priority
    ordered = [dt for dt in _DOC_TYPE_ORDER if dt in doc_types]
    # Include any remaining doc_types not in the standard order
    for dt in doc_types:
        if dt not in ordered and dt != "bank_statement":
            ordered.append(dt)

    results: List[IngestResult] = []

    for doc_type in ordered:
        logger.info(f"[{job_id}] Ingesting doc_type='{doc_type}'...")
        result = await ingest_chunks_for_job(job_id, company_name, doc_type)
        results.append(result)

    total_stored = sum(r.chunks_stored for r in results)
    logger.info(
        f"[{job_id}] All ingest complete: {total_stored} total vectors "
        f"across {len(results)} doc_types"
    )

    return results


# =============================================================================
# Cleanup
# =============================================================================

async def delete_job_chunks(job_id: str) -> int:
    """
    Delete all Qdrant points for a given job_id.

    Uses payload filter on job_id to remove all vectors associated
    with this loan application. Used for cleanup or re-processing.

    Args:
        job_id: Job ID whose vectors should be deleted.

    Returns:
        Count of deleted points (estimated — Qdrant doesn't return exact count).
    """
    import asyncio

    client = get_client()

    # Count points before deletion
    count_before = client.count(
        collection_name=COLLECTION_NAME,
        count_filter=Filter(
            must=[
                FieldCondition(
                    key="job_id",
                    match=MatchValue(value=job_id),
                ),
            ]
        ),
    ).count

    if count_before == 0:
        logger.info(f"[{job_id}] No vectors found in Qdrant — nothing to delete")
        return 0

    # Delete by payload filter
    def _delete():
        client.delete(
            collection_name=COLLECTION_NAME,
            points_selector=FilterSelector(
                filter=Filter(
                    must=[
                        FieldCondition(
                            key="job_id",
                            match=MatchValue(value=job_id),
                        ),
                    ]
                ),
            ),
        )

    await asyncio.to_thread(_delete)

    logger.info(f"[{job_id}] Deleted {count_before} vectors from Qdrant")
    return count_before
