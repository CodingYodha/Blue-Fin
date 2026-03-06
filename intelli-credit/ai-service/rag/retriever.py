"""
RAG Retriever — query-time retrieval from Qdrant.

=============================================================================
At query time:
  1. Embed the query via Jina (single text)
  2. Search Qdrant with metadata filters (job_id, doc_type, section, priority)
  3. Return ranked chunks with cosine similarity scores

Two retrieval modes:
  - retrieve_chunks()          — low-level, any query with custom filters
  - retrieve_for_extraction()  — high-level, maps extraction targets to
                                 optimized query + filter combos

format_chunks_for_prompt() turns retrieved chunks into a clean string for
Claude prompts, with source attribution for every chunk.
=============================================================================
"""

import logging
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field
from qdrant_client.models import Filter, FieldCondition, MatchValue

from .qdrant_client import get_client, COLLECTION_NAME
from .embedder import embed_single

logger = logging.getLogger("rag.retriever")


# =============================================================================
# RetrievedChunk schema
# =============================================================================

class RetrievedChunk(BaseModel):
    """A single chunk retrieved from Qdrant with its similarity score."""

    model_config = ConfigDict(from_attributes=True)

    chunk_text: str = Field(..., description="Raw text of the chunk")
    score: float = Field(..., description="Cosine similarity score (0-1)")
    page_num: int = Field(default=0, description="Page number in source document")
    section_name: str = Field(default="", description="Section name from chunker")
    doc_type: str = Field(default="", description="Document type")
    chunk_index: int = Field(default=0, description="Position within document")
    embed_priority: str = Field(default="MEDIUM", description="Embedding priority")
    source_file: str = Field(default="", description="Original filename")


# =============================================================================
# Extraction target → query + filter mapping
# =============================================================================

EXTRACTION_QUERIES: Dict[str, Dict[str, Any]] = {
    "financial_ratios": {
        "query": "revenue EBITDA profit net worth total debt interest expense",
        "doc_type_filter": "annual_report",
        "top_k": 8,
    },
    "balance_sheet": {
        "query": "balance sheet total assets current assets liabilities equity net worth",
        "doc_type_filter": "annual_report",
        "top_k": 6,
    },
    "cash_flow": {
        "query": "cash flow from operations operating activities debt service",
        "doc_type_filter": "annual_report",
        "top_k": 5,
    },
    "auditor_notes": {
        "query": "auditor qualification emphasis of matter going concern audit report",
        "doc_type_filter": "annual_report",
        "top_k": 4,
    },
    "covenants": {
        "query": "covenant terms conditions loan facility collateral security charge",
        "doc_type_filter": "legal_notice",
        "top_k": 6,
    },
    "litigation": {
        "query": "contingent liabilities legal proceedings pending cases court",
        "doc_type_filter": "annual_report",
        "top_k": 5,
    },
    "related_party": {
        "query": "related party transactions director promoter associated entities payments",
        "doc_type_filter": "annual_report",
        "top_k": 6,
    },
    "rating_rationale": {
        "query": "rating rationale downgrade upgrade outlook key drivers weaknesses",
        "doc_type_filter": "rating_report",
        "top_k": 5,
    },
    "collateral": {
        "query": "collateral security hypothecation mortgage pledge property value",
        "top_k": 5,
        # No doc_type filter — collateral appears in both AR and legal notices
    },
    "management_discussion": {
        "query": "management discussion analysis business performance outlook risks",
        "doc_type_filter": "annual_report",
        "top_k": 6,
    },
}


# =============================================================================
# Core retrieval function
# =============================================================================

async def retrieve_chunks(
    query: str,
    job_id: str,
    top_k: int = 5,
    doc_type_filter: Optional[str] = None,
    section_filter: Optional[str] = None,
    priority_filter: Optional[str] = None,
) -> List[RetrievedChunk]:
    """
    Embed a query and search Qdrant for the most relevant chunks.

    Always scoped to a single job_id. Optional filters narrow down
    by doc_type, section_name, or embed_priority.

    Args:
        query:           Natural language query to embed.
        job_id:          Job ID to scope the search to.
        top_k:           Number of top results to return.
        doc_type_filter: Filter to a specific doc_type (e.g. "annual_report").
        section_filter:  Filter by section_name (keyword match).
        priority_filter: Filter by embed_priority ("HIGH", "MEDIUM", "LOW").

    Returns:
        List of RetrievedChunk sorted by score descending.
    """
    # Step 1: Embed the query
    vector = await embed_single(query)

    # Step 2: Build Qdrant filter
    must_conditions = [
        FieldCondition(
            key="job_id",
            match=MatchValue(value=job_id),
        ),
    ]

    if doc_type_filter:
        must_conditions.append(
            FieldCondition(
                key="doc_type",
                match=MatchValue(value=doc_type_filter),
            )
        )

    if section_filter:
        must_conditions.append(
            FieldCondition(
                key="section_name",
                match=MatchValue(value=section_filter),
            )
        )

    if priority_filter:
        must_conditions.append(
            FieldCondition(
                key="embed_priority",
                match=MatchValue(value=priority_filter),
            )
        )

    search_filter = Filter(must=must_conditions)

    # Step 3: Search Qdrant
    client = get_client()
    results = client.search(
        collection_name=COLLECTION_NAME,
        query_vector=vector,
        query_filter=search_filter,
        limit=top_k,
        with_payload=True,
    )

    # Step 4: Convert to RetrievedChunk
    chunks: List[RetrievedChunk] = []
    for hit in results:
        payload = hit.payload or {}
        chunks.append(
            RetrievedChunk(
                chunk_text=payload.get("chunk_text", ""),
                score=hit.score,
                page_num=payload.get("page_num", 0),
                section_name=payload.get("section_name", ""),
                doc_type=payload.get("doc_type", ""),
                chunk_index=payload.get("chunk_index", 0),
                embed_priority=payload.get("embed_priority", "MEDIUM"),
                source_file=payload.get("source_file", ""),
            )
        )

    logger.info(
        f"Retrieved {len(chunks)} chunks for job_id={job_id} "
        f"(query='{query[:50]}...', top_k={top_k}"
        f"{f', doc_type={doc_type_filter}' if doc_type_filter else ''}"
        f"{f', section={section_filter}' if section_filter else ''}"
        f")"
    )

    return chunks


# =============================================================================
# High-level extraction retrieval
# =============================================================================

async def retrieve_for_extraction(
    job_id: str,
    extraction_target: str,
) -> List[RetrievedChunk]:
    """
    Retrieve chunks optimized for a specific extraction target.

    Maps extraction_target to a pre-defined query + filter combo from
    EXTRACTION_QUERIES. Falls back to raw query if target is unknown.

    Args:
        job_id:            Job ID to scope the search to.
        extraction_target: Semantic label (e.g. "financial_ratios", "covenants").

    Returns:
        List of RetrievedChunk sorted by score descending.
    """
    config = EXTRACTION_QUERIES.get(extraction_target)

    if config is None:
        logger.warning(
            f"Unknown extraction_target '{extraction_target}' — "
            f"falling back to raw query"
        )
        return await retrieve_chunks(
            query=extraction_target,
            job_id=job_id,
            top_k=5,
        )

    return await retrieve_chunks(
        query=config["query"],
        job_id=job_id,
        top_k=config.get("top_k", 5),
        doc_type_filter=config.get("doc_type_filter"),
        section_filter=config.get("section_filter"),
        priority_filter=config.get("priority_filter"),
    )


# =============================================================================
# Prompt formatting
# =============================================================================

def format_chunks_for_prompt(chunks: List[RetrievedChunk]) -> str:
    """
    Format retrieved chunks into a clean string for Claude prompts.

    Each chunk is prefixed with a source attribution line so Claude can
    cite its sources — every extracted figure traces back to a specific
    page and section.

    Format per chunk:
      [SOURCE: {doc_type} | Page {page_num} | Section: {section_name}]
      {chunk_text}

    Args:
        chunks: List of RetrievedChunk from retrieval.

    Returns:
        Formatted string ready for inclusion in a Claude prompt.
    """
    if not chunks:
        return "[No relevant document chunks found]"

    parts: List[str] = []
    for chunk in chunks:
        header = (
            f"[SOURCE: {chunk.doc_type} | "
            f"Page {chunk.page_num} | "
            f"Section: {chunk.section_name}]"
        )
        parts.append(f"{header}\n{chunk.chunk_text}")

    return "\n\n".join(parts)
