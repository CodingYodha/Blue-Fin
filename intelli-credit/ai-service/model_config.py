"""
Centralized Model Configuration — single source of truth for all AI model names.

=============================================================================
Change models here to swap them across the entire ai-service.
Each constant has a comment indicating which module(s) use it.

After changing a model name here, the change propagates automatically —
no need to edit individual modules.
=============================================================================
"""

# ---------------------------------------------------------------------------
# Claude / Anthropic Models
# ---------------------------------------------------------------------------

# Used in: deep_learning/info_extractor.py → extract_financial_ratios()
# Purpose: Extracts structured financial data (revenue, EBITDA, debt, etc.) from document text
CLAUDE_FINANCIAL_EXTRACTION_MODEL = "claude-haiku-4-5-20251001"

# Used in: deep_learning/info_extractor.py → extract_entities()
# Purpose: NER — extracts promoters, companies, lenders, guarantors for Entity Graph
CLAUDE_ENTITY_EXTRACTION_MODEL = "claude-haiku-4-5-20251001"

# Used in: research_agent.py → classify_document()
# Purpose: Classifies research documents into categories (financial, legal, regulatory, etc.)
CLAUDE_RESEARCH_AGENT_MODEL = "claude-haiku-4-5-20251001"

# Used in: rag/extractor.py (upcoming) → Claude RAG extraction calls
# Purpose: Takes retrieved chunks + prompt, returns structured JSON for LightGBM features
CLAUDE_RAG_EXTRACTION_MODEL = "claude-haiku-4-5-20251001"


# ---------------------------------------------------------------------------
# Jina AI Embedding Models
# ---------------------------------------------------------------------------

# Used in: rag/embedder.py → embed_texts(), embed_single(), embed_chunks_batched()
# Purpose: Text → 768-dim vector embeddings for Qdrant storage and retrieval
# Context window: 8192 tokens (handles financial paragraphs of 800-1200 tokens whole)
JINA_EMBEDDING_MODEL = "jina-embeddings-v2-base-en"

# Dimension of the embedding vector (must match the model above)
# Used in: rag/qdrant_client.py → collection vector config
JINA_EMBEDDING_DIM = 768
