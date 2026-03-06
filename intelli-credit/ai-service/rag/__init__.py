"""
RAG module — Retrieval Augmented Generation pipeline for Intelli-Credit.

Sub-modules:
  - qdrant_client : Qdrant connection singleton, collection setup, health check
"""

from .qdrant_client import (
    get_client,
    ensure_collection_exists,
    qdrant_health_check,
    COLLECTION_NAME,
    VECTOR_DIM,
)

__all__ = [
    "get_client",
    "ensure_collection_exists",
    "qdrant_health_check",
    "COLLECTION_NAME",
    "VECTOR_DIM",
]
