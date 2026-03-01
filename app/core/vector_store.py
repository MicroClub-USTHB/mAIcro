

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence, Union

from qdrant_client import QdrantClient
from qdrant_client.http import models as qdrant_models

from app.core.config import settings
from app.core.embeddings import get_document_embedding_service, get_query_embedding_service
from app.schemas.documents import Document, DocumentMetadata

import logging


class QdrantVectorStore:
	def __init__(self) -> None:
		"""
		Initialize the Qdrant vector store client and ensure the collection exists.
		Uses config-driven embedding services and collection settings.
		"""
		self.client = QdrantClient(path=settings.VECTORSTORE_PATH)
		self.collection_name = settings.VECTORSTORE_COLLECTION
		self.doc_embedder = get_document_embedding_service()
		self.query_embedder = get_query_embedding_service()
		try:
			# Always recreate to ensure vectors_config is present and correct
			if self.collection_name in [c.name for c in self.client.get_collections().collections]:
				self.client.delete_collection(collection_name=self.collection_name)
				logging.info(f"Deleted existing Qdrant collection: {self.collection_name}")
			self.client.create_collection(
				collection_name=self.collection_name,
				vectors_config=qdrant_models.VectorParams(
					size=self.doc_embedder.output_dimensionality,
					distance=qdrant_models.Distance.COSINE
				)
			)
		except Exception as e:
			logging.error(f"Failed to initialize Qdrant collection: {e}")
			raise

	@staticmethod
	def _serialize_value(value: Any) -> Any:
		"""
		Recursively serialize payload values (e.g., datetimes -> isoformat strings).
		Ensures all metadata is JSON-serializable for Qdrant storage.
		"""
		if isinstance(value, datetime):
			return value.isoformat()
		if isinstance(value, dict):
			return {k: QdrantVectorStore._serialize_value(v) for k, v in value.items()}
		if isinstance(value, list):
			return [QdrantVectorStore._serialize_value(v) for v in value]
		return value

	@staticmethod
	def document_to_payload(document: Document, schema_version: str = "1") -> Dict[str, Any]:
		"""
		Convert a Document model to a Qdrant payload dict without mutating the source.
		Used for storing documents with all metadata in Qdrant.
		"""
		meta_dict = document.metadata.model_dump()
		payload: Dict[str, Any] = QdrantVectorStore._serialize_value(meta_dict.copy())
		payload["text"] = document.text
		payload.setdefault("document", document.text)  # backward compatibility
		payload["_schema_version"] = schema_version
		return payload

	@staticmethod
	def payload_to_document(point_id: Union[str, int], payload: Dict[str, Any]) -> Document:
		"""
		Convert a Qdrant payload back to a Document model.
		Used for reconstructing documents from Qdrant search results.
		"""
		meta = DocumentMetadata(
			channel=payload.get("channel"),
			author=payload.get("author"),
			timestamp=payload.get("timestamp"),
			attributes=payload.get("attributes", {}),
		)
		return Document(id=str(point_id), text=payload.get("text") or payload.get("document", ""), metadata=meta)

	@staticmethod
	def _validate_and_prepare_documents(
		documents: Sequence[str],
		metadatas: Optional[Sequence[Dict[str, Any]]],
		ids: Optional[Sequence[Union[str, int]]]
	) -> tuple:
		"""
		Validate and prepare documents for addition to Qdrant.
		Returns a tuple of (texts, payloads, ids).
		"""
		if not documents:
			raise ValueError("'documents' must be a non-empty sequence of strings.")
		if any(not isinstance(doc, str) or not doc for doc in documents):
			raise ValueError("All documents must be non-empty strings.")
		n = len(documents)
		if ids is not None and len(ids) != n:
			raise ValueError("'ids' must be the same length as 'documents'.")
		if metadatas is not None and len(metadatas) != n:
			raise ValueError("'metadatas' must be the same length as 'documents'.")
		if ids is not None:
			if any(id_ is None or id_ == "" for id_ in ids):
				raise ValueError("All 'ids' must be non-empty when provided.")
			if len(set(ids)) != len(ids):
				raise ValueError("Duplicate IDs detected in 'ids'.")
		payloads = metadatas if metadatas is not None else [{} for _ in documents]
		return documents, payloads, ids

	def add_documents(
		self,
		documents: Sequence[str],
		metadatas: Optional[Sequence[Dict[str, Any]]] = None,
		ids: Optional[Sequence[Union[str, int]]] = None,
		schema_version: str = "1",
	) -> None:
		"""
		Embed and add raw text documents to the Qdrant collection.
		Uses manual embeddings (doc_embedder) to match the collection vector size.
		"""
		try:
			texts, payloads, ids = self._validate_and_prepare_documents(documents, metadatas, ids)
			vectors = self.doc_embedder.embed_texts(list(texts))
			points: List[qdrant_models.PointStruct] = []
			for i, (vec, doc) in enumerate(zip(vectors, texts)):
				point_id = ids[i] if ids is not None else i
				payload = payloads[i].copy()
				payload["text"] = doc
				payload.setdefault("document", doc)
				payload["_schema_version"] = schema_version
				serialized_payload = self._serialize_value(payload)
				points.append(qdrant_models.PointStruct(
					id=point_id,
					vector=vec,
					payload=serialized_payload
				))
			self.client.upsert(collection_name=self.collection_name, points=points)
		except Exception as e:
			logging.error(f"Failed to add documents to Qdrant: {e}")
			raise

	def add_document_models(self, documents: Sequence[Document], schema_version: str = "1") -> None:
		"""
		Convenience method to add Pydantic Document models.
		Extracts text, metadata, and IDs from Document objects and stores them in Qdrant.
		"""
		if not documents:
			raise ValueError("'documents' must be a non-empty sequence of Document models.")
		texts = [doc.text for doc in documents]
		payloads = [self.document_to_payload(doc, schema_version=schema_version) for doc in documents]
		ids = [doc.id for doc in documents]
		self.add_documents(texts, metadatas=payloads, ids=ids, schema_version=schema_version)

	def similarity_search(self, query: str, n_results: int = 5, where: Optional[Dict[str, Any]] = None):
		"""
		Embed the query using the same embedding service as documents and search using query_vector.
		Uses client.search to avoid Fastembed query_text requirements.
		"""
		try:
			if not query or not isinstance(query, str):
				raise ValueError("Query must be a non-empty string.")
			q_vec = self.query_embedder.embed_text(query)
			filter_ = None
			if where:
				filter_ = qdrant_models.Filter(must=[
					qdrant_models.FieldCondition(
						key=k,
						match=qdrant_models.MatchValue(value=v)
					) for k, v in where.items()
				])
			search_result = self.client.query_points(
				collection_name=self.collection_name,
				query=q_vec,
				limit=n_results,
				query_filter=filter_
			)
			return search_result.points
		except Exception as e:
			logging.error(f"Similarity search failed: {e}")
			raise
