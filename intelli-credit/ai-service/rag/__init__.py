"""
RAG module — Retrieval Augmented Generation pipeline for Intelli-Credit.

Sub-modules:
  - qdrant_client : Qdrant connection singleton, collection setup, health check
  - embedder      : Jina AI cloud API embedding (768-dim, batch of 32)
  - ingestor      : Reads Go service chunks, embeds, stores in Qdrant
"""

from .qdrant_client import (
    get_client,
    ensure_collection_exists,
    qdrant_health_check,
    COLLECTION_NAME,
    VECTOR_DIM,
)
from .embedder import (
    embed_texts,
    embed_single,
    embed_chunks_batched,
    ChunkInput,
    ChunkEmbedding,
    JINA_MODEL,
)
from .ingestor import (
    ingest_chunks_for_job,
    ingest_all_documents,
    delete_job_chunks,
    assign_embed_priority,
    IngestResult,
)

__all__ = [
    "get_client",
    "ensure_collection_exists",
    "qdrant_health_check",
    "COLLECTION_NAME",
    "VECTOR_DIM",
    "embed_texts",
    "embed_single",
    "embed_chunks_batched",
    "ChunkInput",
    "ChunkEmbedding",
    "JINA_MODEL",
    "ingest_chunks_for_job",
    "ingest_all_documents",
    "delete_job_chunks",
    "assign_embed_priority",
    "IngestResult",
]
