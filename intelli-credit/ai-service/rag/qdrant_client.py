"""
Qdrant Client — connection singleton, collection management, and health check.

=============================================================================
Qdrant runs at http://qdrant:6333 inside Docker (service name: qdrant).
For local dev outside Docker: http://localhost:6333.

ONE collection is used for all documents across all jobs. job_id is a
payload filter, not a separate collection. This is correct Qdrant design —
collections are expensive to create, payload filters are cheap.

Collection: intelli_credit_chunks
Vector dim: 768 (Jina jina-embeddings-v2-base-en)
Distance:   Cosine

Payload indexes (for fast filtered search):
  - job_id         (KEYWORD)
  - doc_type       (KEYWORD)
  - section_name   (KEYWORD)
  - embed_priority (KEYWORD)
=============================================================================
"""

import logging
import os

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PayloadSchemaType

logger = logging.getLogger("rag.qdrant_client")

# =============================================================================
# Constants
# =============================================================================

COLLECTION_NAME = "intelli_credit_chunks"

# Jina's jina-embeddings-v2-base-en produces 768-dimensional vectors
VECTOR_DIM = 768

# =============================================================================
# Chunk payload schema (for reference — enforced by the ingest pipeline)
# =============================================================================
# Every vector stored in Qdrant has this payload (metadata):
# {
#   "job_id":          str,   ← which loan application this chunk belongs to
#   "company_name":    str,   ← borrower company name
#   "doc_type":        str,   ← "annual_report" | "rating_report" | "legal_notice" | "gst_filing"
#   "page_num":        int,   ← page number in source document
#   "section_name":    str,   ← e.g. "Management Discussion", "Balance Sheet"
#   "chunk_index":     int,   ← position of this chunk within its document
#   "chunk_text":      str,   ← the raw text of the chunk (stored for retrieval)
#   "embed_priority":  str,   ← "HIGH" | "MEDIUM" | "LOW"
#   "char_count":      int,   ← length of chunk_text
#   "source_file":     str    ← original filename
# }


# =============================================================================
# Connection singleton
# =============================================================================

_client: QdrantClient | None = None


def get_client() -> QdrantClient:
    """
    Return a module-level Qdrant client singleton.

    Reads QDRANT_HOST and QDRANT_PORT from environment.
    Defaults: host=qdrant, port=6333.
    """
    global _client
    if _client is None:
        host = os.environ.get("QDRANT_HOST", "qdrant")
        port = int(os.environ.get("QDRANT_PORT", "6333"))
        _client = QdrantClient(host=host, port=port)
        logger.info(f"Qdrant client connected: {host}:{port}")
    return _client


def close_client():
    """Close the Qdrant client (for shutdown)."""
    global _client
    if _client is not None:
        _client.close()
        _client = None
        logger.info("Qdrant client closed")


# =============================================================================
# Collection setup (run once at startup)
# =============================================================================

def ensure_collection_exists(client: QdrantClient | None = None):
    """
    Create the intelli_credit_chunks collection if it doesn't already exist.

    Creates payload indexes for fast filtered search on:
      - job_id, doc_type, section_name, embed_priority

    Args:
        client: Optional QdrantClient. Uses singleton if not provided.
    """
    if client is None:
        client = get_client()

    existing = [c.name for c in client.get_collections().collections]

    if COLLECTION_NAME in existing:
        logger.info(
            f"Qdrant collection '{COLLECTION_NAME}' already exists — skipping creation"
        )
        return

    # Create collection with cosine similarity
    client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=VectorParams(
            size=VECTOR_DIM,
            distance=Distance.COSINE,
        ),
    )
    logger.info(
        f"Created Qdrant collection '{COLLECTION_NAME}' "
        f"(dim={VECTOR_DIM}, distance=COSINE)"
    )

    # Create payload indexes for fast filtered search
    for field_name in ("job_id", "doc_type", "section_name", "embed_priority"):
        client.create_payload_index(
            collection_name=COLLECTION_NAME,
            field_name=field_name,
            field_schema=PayloadSchemaType.KEYWORD,
        )
        logger.info(f"Created payload index: {field_name} (KEYWORD)")


# =============================================================================
# Health check
# =============================================================================

def qdrant_health_check() -> bool:
    """
    Check Qdrant connectivity by listing collections.

    Returns:
        True if Qdrant is reachable, False otherwise.
    """
    try:
        client = get_client()
        client.get_collections()
        return True
    except Exception as e:
        logger.warning(f"Qdrant health check failed: {e}")
        return False
