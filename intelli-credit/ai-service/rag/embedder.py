"""
Jina AI Embedder — calls Jina cloud API to embed text into vectors.

=============================================================================
Model: jina-embeddings-v2-base-en
  - 768 dimensions
  - 8192 token context window (handles financial paragraphs of 800-1200 tokens
    without truncation — this is why Jina was chosen over OpenAI embeddings)

API endpoint: https://api.jina.ai/v1/embeddings
Auth: Bearer token from JINA_API_KEY environment variable

Batch size: max 32 texts per API call (Jina rate-limit safe zone).
Inter-batch delay: 0.5 seconds to respect rate limits.
=============================================================================
"""

import asyncio
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List

import httpx

from model_config import JINA_EMBEDDING_MODEL

logger = logging.getLogger("rag.embedder")

# =============================================================================
# Constants
# =============================================================================

JINA_API_URL = "https://api.jina.ai/v1/embeddings"
JINA_MODEL = JINA_EMBEDDING_MODEL  # re-export for backward compatibility
BATCH_SIZE = 32          # max texts per API call
INTER_BATCH_DELAY = 0.5  # seconds between batches


# =============================================================================
# Data classes
# =============================================================================

@dataclass
class ChunkInput:
    """Input to the batch embedder: text + metadata."""
    chunk_text: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ChunkEmbedding:
    """Output from the batch embedder: text + vector + metadata."""
    chunk_text: str
    vector: List[float]
    metadata: Dict[str, Any] = field(default_factory=dict)


# =============================================================================
# Core embedding function
# =============================================================================

async def embed_texts(texts: List[str]) -> List[List[float]]:
    """
    Embed a list of texts via the Jina AI cloud API.

    Automatically splits into batches of 32 if needed. Each batch is a
    separate API call; results are concatenated in order.

    Args:
        texts: List of text strings to embed.

    Returns:
        List of 768-dim float vectors, one per input text.

    Raises:
        ValueError: If JINA_API_KEY is not set.
        httpx.HTTPStatusError: If the Jina API returns an error.
    """
    api_key = os.environ.get("JINA_API_KEY")
    if not api_key:
        raise ValueError(
            "JINA_API_KEY not set. Add it to .env or environment variables."
        )

    if not texts:
        return []

    all_embeddings: List[List[float]] = []
    total_batches = (len(texts) + BATCH_SIZE - 1) // BATCH_SIZE
    start_time = time.perf_counter()

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        for batch_idx in range(total_batches):
            batch_start = batch_idx * BATCH_SIZE
            batch_end = min(batch_start + BATCH_SIZE, len(texts))
            batch = texts[batch_start:batch_end]

            payload = {
                "model": JINA_MODEL,
                "input": batch,
            }

            response = await client.post(
                JINA_API_URL,
                headers=headers,
                json=payload,
            )

            if response.status_code != 200:
                error_body = response.text
                logger.error(
                    f"Jina API error (HTTP {response.status_code}): {error_body}"
                )
                raise httpx.HTTPStatusError(
                    message=f"Jina embedding failed: HTTP {response.status_code} — {error_body}",
                    request=response.request,
                    response=response,
                )

            data = response.json()
            batch_embeddings = [
                item["embedding"] for item in data["data"]
            ]
            all_embeddings.extend(batch_embeddings)

            logger.info(
                f"Embedded batch {batch_idx + 1}/{total_batches} "
                f"({len(batch)} texts)"
            )

            # Rate-limit delay between batches (skip after last batch)
            if batch_idx < total_batches - 1:
                await asyncio.sleep(INTER_BATCH_DELAY)

    elapsed = time.perf_counter() - start_time
    rate = len(texts) / elapsed if elapsed > 0 else 0

    logger.info(
        f"Embedding complete: {len(texts)} texts in {elapsed:.2f}s "
        f"({rate:.1f} texts/sec)"
    )

    return all_embeddings


# =============================================================================
# Convenience wrappers
# =============================================================================

async def embed_single(text: str) -> List[float]:
    """
    Embed a single text string. Convenience wrapper for query-time use.

    Args:
        text: A single text string to embed.

    Returns:
        768-dim float vector.
    """
    vectors = await embed_texts([text])
    return vectors[0]


async def embed_chunks_batched(
    chunks: List[ChunkInput],
) -> List[ChunkEmbedding]:
    """
    Embed a list of ChunkInput objects in batches of 32.

    Preserves chunk metadata alongside the computed vector.
    Adds a 0.5s delay between batches to respect Jina API rate limits.

    Args:
        chunks: List of ChunkInput with text and metadata.

    Returns:
        List of ChunkEmbedding pairing each chunk with its vector.
    """
    if not chunks:
        return []

    texts = [c.chunk_text for c in chunks]
    vectors = await embed_texts(texts)

    results = [
        ChunkEmbedding(
            chunk_text=chunk.chunk_text,
            vector=vector,
            metadata=chunk.metadata,
        )
        for chunk, vector in zip(chunks, vectors)
    ]

    return results
