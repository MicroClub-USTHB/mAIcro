"""
Knowledge retrieval service — high-level wrapper around the vector store.

This is the service layer that the rest of the app uses to add and search knowledge.
It hides the details of embeddings and Qdrant behind two simple methods:
  - add_knowledge():    store text chunks (auto-embeds and uploads them)
  - search_knowledge(): find the most relevant chunks for a query
"""

from typing import Optional, Sequence, Type

from app.core.config import settings
from app.core.vector_store import QdrantVectorStore, VectorStoreUploadOptions
from app.schemas.documents import BaseSchema, SCHEMA_REGISTRY


class KnowledgeRetrievalService:
    """Provides add/search methods on top of the Qdrant vector store."""

    def __init__(self):
        # Initialize the vector store (creates/validates the collection on startup)
        self.vector_store = QdrantVectorStore()

    def add_knowledge(
        self,
        chunks,
        metadatas=None,
        ids=None,
        schema_version: Optional[Type[BaseSchema]] = None,
        options: Optional[VectorStoreUploadOptions] = None,
    ):
        """
        Store text chunks as embeddings in the vector store.

        Args:
          chunks:         list of text strings to store
          metadatas:      optional list of metadata dicts (one per chunk)
          ids:            optional list of unique IDs (one per chunk)
          schema_version: which schema to tag these docs with (defaults to current)
          options:        advanced upload options (batch size, retries, etc.)
        """
        version = schema_version or SCHEMA_REGISTRY[settings.CURRENT_SCHEMA_VERSION]
        upload_options = options or VectorStoreUploadOptions(schema_version=version)
        self.vector_store.add_documents(chunks, metadatas=metadatas, ids=ids, options=upload_options)

    def search_knowledge(self, query, n_results=5, where=None):
        """
        Find the most relevant stored chunks for a user query.

        Args:
          query:     the search text
          n_results: how many results to return (default 5)
          where:     optional metadata filter (e.g. {"channel": "general"})

        Returns: list of Qdrant ScoredPoint objects, ranked by similarity.
        """
        return self.vector_store.similarity_search(query, n_results=n_results, where=where)
