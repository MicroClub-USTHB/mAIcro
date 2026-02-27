"""Utilities for turning text into Gemini embeddings.

The main entry point is EmbeddingService, which hides the google-genai
client behind a simple "text in, vector out" interface that the rest of
the app can reuse in ingestion and query flows.
"""

from __future__ import annotations

from typing import Iterable, List, Literal, Sequence

import numpy as np
from google import genai
from google.genai import types as genai_types

from app.core.config import settings


GeminiEmbeddingTask = Literal[
	"RETRIEVAL_DOCUMENT",
	"RETRIEVAL_QUERY",
]


class EmbeddingService:
	"""Small helper around Gemini's embedding model.

	By default it is configured for RAG-style usage:

	- `RETRIEVAL_DOCUMENT` when embedding documents or chunks
	- `RETRIEVAL_QUERY` when embedding user questions
	"""

	def __init__(
		self,
		model: str = "gemini-embedding-001",
		output_dimensionality: int = 768,
		task_type: GeminiEmbeddingTask = "RETRIEVAL_DOCUMENT",
	) -> None:
		self.model = model
		self.output_dimensionality = output_dimensionality
		self.task_type: GeminiEmbeddingTask = task_type

		# The client reads credentials (API key, project) from env/.config
		self._client = genai.Client()

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
		"""Embed a single piece of text and return a vector."""

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
		"""Embed many texts at once.

		The order of vectors matches the order of the input texts.
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
		model="gemini-embedding-001",
		output_dimensionality=768,
		task_type="RETRIEVAL_DOCUMENT",
	)


def get_query_embedding_service() -> EmbeddingService:
	"""Factory for embedding user queries for retrieval."""

	return EmbeddingService(
		model="gemini-embedding-001",
		output_dimensionality=768,
		task_type="RETRIEVAL_QUERY",
	)


__all__ = [
	"EmbeddingService",
	"get_document_embedding_service",
	"get_query_embedding_service",
]

