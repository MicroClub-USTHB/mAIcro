"""
Embedding service — converts text into vectors using Gemini.

Two factory functions create ready-to-use services:
  - get_document_embedding_service(): for embedding documents (uses RETRIEVAL_DOCUMENT task type)
  - get_query_embedding_service():    for embedding queries  (uses RETRIEVAL_QUERY task type)

Using different task types for documents vs queries improves retrieval quality
because Gemini optimizes the embedding space differently for each.
"""

from __future__ import annotations

import logging
import time
from typing import Iterable, List, Sequence

import numpy as np
from google import genai
from google.genai import types as genai_types

from app.core.config import settings


class EmbeddingService:
    """
    Wraps Gemini's embedding API.
    Handles single text, batch text, retry logic, and vector normalization.
    """

    def __init__(
        self,
        model: str,
        output_dimensionality: int,
        task_type: str,
    ) -> None:
        self.model = model
        self.output_dimensionality = output_dimensionality
        self.task_type: str = task_type

        # Create Gemini client using the API key from config
        self._client = genai.Client(api_key=settings.GEMINI_API_KEY)

    def _build_config(self) -> genai_types.EmbedContentConfig:
        """Build the config object that Gemini's API expects."""
        return genai_types.EmbedContentConfig(
            task_type=self.task_type,
            output_dimensionality=self.output_dimensionality,
        )

    def _normalize(self, vector: Sequence[float]) -> List[float]:
        """
        Scale a vector to unit length (L2 norm = 1).
        This makes cosine similarity equivalent to dot product, which is faster.
        Zero vectors are returned as-is to avoid division by zero.
        """
        arr = np.asarray(vector, dtype=float)
        norm = float(np.linalg.norm(arr))
        if norm == 0.0:
            return arr.tolist()
        return (arr / norm).tolist()

    def _embed_with_retry(self, contents):
        """
        Call the Gemini embedding API with automatic retry on failure.

        Uses exponential backoff: 1s → 2s → 4s (base_delay * 2^attempt).
        Both max_retries and base_delay are configurable via settings.
        If all retries fail, raises RuntimeError with the last exception.
        """
        max_retries = settings.EMBEDDING_MAX_RETRIES
        base_delay = settings.EMBEDDING_RETRY_BASE_DELAY
        last_exc = None
        for attempt in range(max_retries):
            try:
                return self._client.models.embed_content(
                    model=self.model,
                    contents=contents,
                    config=self._build_config(),
                )
            except Exception as exc:
                last_exc = exc
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)
                    logging.warning(
                        "Embedding API call failed (attempt %d/%d): %s. Retrying in %.1fs...",
                        attempt + 1, max_retries, exc, delay,
                    )
                    time.sleep(delay)
        raise RuntimeError(
            f"Embedding API call failed after {max_retries} attempts"
        ) from last_exc

    def embed_text(self, text: str) -> List[float]:
        """
        Embed a single text string → returns one normalized vector.
        Used for embedding search queries.
        """
        if not text:
            raise ValueError("Text to embed must be non-empty")

        result = self._embed_with_retry(text)
        # Unpack the single embedding from the response
        [embedding_obj] = result.embeddings
        return self._normalize(embedding_obj.values)

    def embed_texts(self, texts: Iterable[str]) -> List[List[float]]:
        """
        Embed multiple texts in one API call → returns a list of normalized vectors.
        Used for embedding documents during ingestion.

        Callers are responsible for chunking large batches before calling
        this method to avoid API payload limits.
        """
        texts_list = [t for t in texts]
        if not texts_list:
            return []
        if any(not t for t in texts_list):
            raise ValueError("All texts must be non-empty when embedding a batch")

        result = self._embed_with_retry(texts_list)
        return [self._normalize(e.values) for e in result.embeddings]


# ── Factory functions ────────────────────────────────────────────────────────
# These create embedding services with the right task type from config.

def get_document_embedding_service() -> EmbeddingService:
    """Create an embedding service configured for documents (ingestion)."""
    return EmbeddingService(
        model=settings.EMBEDDING_MODEL_NAME,
        output_dimensionality=settings.EMBEDDING_DIM,
        task_type=settings.EMBEDDING_TASK_TYPES["document"],
    )


def get_query_embedding_service() -> EmbeddingService:
    """Create an embedding service configured for queries (search)."""
    return EmbeddingService(
        model=settings.EMBEDDING_MODEL_NAME,
        output_dimensionality=settings.EMBEDDING_DIM,
        task_type=settings.EMBEDDING_TASK_TYPES["query"],
    )


__all__ = [
    "EmbeddingService",
    "get_document_embedding_service",
    "get_query_embedding_service",
]

if __name__ == "__main__":
    # Quick test to verify embedding service works and metadata tracking
    from app.schemas.documents import Document, DocumentMetadata, SCHEMA_REGISTRY
    embedding_service = get_document_embedding_service()
    test_text = "Depresso rah mkouli"
    embedding = embedding_service.embed_text(test_text)
    from app.core.config import settings
    meta = DocumentMetadata(
        channel="general",
        author="user",
        timestamp=None,
        attributes={},
        schema_version=SCHEMA_REGISTRY[settings.CURRENT_SCHEMA_VERSION],
        embedding_model=embedding_service.model,
        embedding_dim=embedding_service.output_dimensionality
    )
    doc = Document(id="test", text=test_text, metadata=meta)
    print(f"Embedding for '{test_text}': {embedding[:5]}... (length {len(embedding)})")
    print(f"Document metadata: {doc.metadata}")