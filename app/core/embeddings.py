"""
Embedding utilities for Gemini models.

This module provides the EmbeddingService class, which wraps Gemini's embedding API
in a config-driven, flexible interface for both single and batch text embedding.
All model, dimensionality, and task type parameters are sourced from config, allowing
easy customization and extension. Use get_document_embedding_service() and
get_query_embedding_service() to obtain ready-to-use embedding services for RAG pipelines.
"""

from __future__ import annotations

from typing import Iterable, List, Literal, Sequence

import numpy as np
from google import genai
from google.genai import types as genai_types

from app.core.config import settings


class EmbeddingService:
    """
    Service for generating embeddings using Gemini models.

    - Fully config-driven: model, output_dimensionality, and task_type are provided at instantiation.
    - Supports both single (embed_text) and batch (embed_texts) embedding for efficient workflows.
    - Use get_document_embedding_service() and get_query_embedding_service() for standard RAG usage.
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

        # The client reads credentials (API key, project) from env/.config
        self._client = genai.Client(api_key=settings.GEMINI_API_KEY)

    def _build_config(self) -> genai_types.EmbedContentConfig:
        return genai_types.EmbedContentConfig(
            task_type=self.task_type,
            output_dimensionality=self.output_dimensionality,
        )

    def _normalize(self, vector: Sequence[float]) -> List[float]:
        arr = np.asarray(vector, dtype=float)
        norm = float(np.linalg.norm(arr))
        if norm == 0.0:
            return arr.tolist()
        return (arr / norm).tolist()

    def embed_text(self, text: str) -> List[float]:
        """
        Converts a single string of text into a vector (embedding) that represents its meaning.
        This is useful when you want to compare a user query or a document to other texts using vector similarity.
        Returns a normalized vector (list of floats) for the input text.
        Raises ValueError if the input text is empty.
        Example use: Embedding a user question before searching for similar documents.
        """

        if not text:
            raise ValueError("Text to embed must be non-empty")

        result = self._client.models.embed_content(
            model=self.model,
            contents=text,
            config=self._build_config(),
        )

        [embedding_obj] = result.embeddings
        return self._normalize(embedding_obj.values)

    def embed_texts(self, texts: Iterable[str]) -> List[List[float]]:
        """
        Converts a list of texts into a list of vectors (embeddings), one for each text.
        This is much faster and more efficient than embedding each text one by one, especially for large datasets.
        The output is a list of normalized vectors, in the same order as the input texts.
        Raises ValueError if any input text is empty.
        Example use: Embedding all documents in your database before storing them in a vector store.
        """

        texts_list = [t for t in texts]
        if not texts_list:
            return []
        if any(not t for t in texts_list):
            raise ValueError("All texts must be non-empty when embedding a batch")

        result = self._client.models.embed_content(
            model=self.model,
            contents=texts_list,
            config=self._build_config(),
        )

        return [self._normalize(e.values) for e in result.embeddings]


def get_document_embedding_service() -> EmbeddingService:
    """Factory for embedding documents/chunks for retrieval."""

    return EmbeddingService(
        model=settings.EMBEDDING_MODEL_NAME,
        output_dimensionality=settings.EMBEDDING_DIM,
        task_type=settings.EMBEDDING_TASK_TYPES["document"],
    )


def get_query_embedding_service() -> EmbeddingService:
    """Factory for embedding user queries for retrieval."""

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
    # Quick test to verify embedding service works
    service = get_document_embedding_service()
    test_text = "Depresso rah mkouli"
    embedding = service.embed_text(test_text)
    print(f"Embedding for '{test_text}': {embedding[:5]}... (length {len(embedding)})")