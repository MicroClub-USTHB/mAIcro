
"""
Vector store — stores and retrieves document embeddings using Qdrant.

This is the core storage layer. It handles:
  1. Creating/validating the Qdrant collection on startup
  2. Converting Document models ↔ Qdrant payload dicts
  3. Embedding text and uploading vectors to Qdrant
  4. Running similarity searches against stored vectors

Main entry points:
  - add_documents():      upload raw strings (auto-embeds them)
  - add_document_models(): upload Document model objects
  - similarity_search():  find documents most similar to a query
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional, Sequence, Type, Union
import logging

from qdrant_client import QdrantClient
from qdrant_client.http import models as qdrant_models

from app.core.config import settings
from app.core.embeddings import get_document_embedding_service, get_query_embedding_service
from app.schemas.documents import BaseSchema, Document, DocumentMetadata, SCHEMA_REGISTRY, get_document_class


# ── Upload Options ───────────────────────────────────────────────────────────

@dataclass(frozen=True)
class VectorStoreUploadOptions:
	"""
	Groups all upload-time settings into one object.
	Frozen (immutable) so options can't be mutated after creation.
	"""

	# Which schema version to tag documents with (defaults to current version from config)
	schema_version: Type[BaseSchema] = field(default_factory=lambda: SCHEMA_REGISTRY[settings.CURRENT_SCHEMA_VERSION])

	wait: bool = True                  # Wait for Qdrant to confirm the upload
	batch_size: Optional[int] = None   # How many docs to upload per batch (None = use store default)
	parallel: int = 1                  # Number of parallel upload threads
	max_retries: Optional[int] = None  # Retry count for failed uploads (None = use store default)

	# UPSERT = insert or update if ID already exists
	update_mode: qdrant_models.UpdateMode = qdrant_models.UpdateMode.UPSERT


# ── Main Vector Store Class ──────────────────────────────────────────────────

class QdrantVectorStore:
	"""
	Manages a single Qdrant collection for document storage and retrieval.
	Uses two separate embedding services: one for documents, one for queries.
	"""

	def __init__(
		self,
		payload_indexes=None,
		batch_size=None,
		max_retries=None
	):
		# Connect to the local Qdrant database (file-based, no server needed)
		self.client = QdrantClient(path=settings.VECTORSTORE_PATH)
		self.collection_name = settings.VECTORSTORE_COLLECTION

		# Create embedding services: one tuned for documents, one for queries
		self.doc_embedder = get_document_embedding_service()
		self.query_embedder = get_query_embedding_service()

		# Use provided values or fall back to config defaults
		self.payload_indexes = payload_indexes or settings.VECTORSTORE_PAYLOAD_INDEXES
		self.batch_size = batch_size or settings.VECTORSTORE_BATCH_SIZE
		self.max_retries = max_retries or settings.VECTORSTORE_MAX_RETRIES

		# Make sure the collection exists and has the right indexes
		try:
			self._ensure_collection()
			self._ensure_payload_indexes()
		except Exception as e:
			logging.error(f"Failed to initialize Qdrant collection: {e}")
			raise

	# ── Collection Setup ─────────────────────────────────────────────────

	def _ensure_collection(self) -> None:
		"""
		If the collection doesn't exist → create it.
		If it does exist → verify vector size and distance metric match config.
		Raises ValueError if there's a mismatch.
		"""
		existing_collections = {collection.name for collection in self.client.get_collections().collections}

		if self.collection_name not in existing_collections:
			# Collection doesn't exist yet — create it with our vector config
			distance_metric = getattr(qdrant_models.Distance, settings.VECTORSTORE_DISTANCE.upper(), qdrant_models.Distance.COSINE)
			self.client.create_collection(
				collection_name=self.collection_name,
				vectors_config=qdrant_models.VectorParams(
					size=self.doc_embedder.output_dimensionality,
					distance=distance_metric,
				),
			)
			logging.info(f"Created Qdrant collection: {self.collection_name}")
			return

		# Collection already exists — check that it matches our config
		collection_info = self.client.get_collection(self.collection_name)
		vectors_config = collection_info.config.params.vectors
		configured_size = getattr(vectors_config, "size", None)
		configured_distance = getattr(vectors_config, "distance", None)

		# Vector size must match the embedding model's output dimension
		if configured_size != self.doc_embedder.output_dimensionality:
			raise ValueError(
				f"Existing collection '{self.collection_name}' uses vector size {configured_size}, "
				f"but the embedding service is configured for {self.doc_embedder.output_dimensionality}."
			)

		# Distance metric must match config (COSINE, DOT, EUCLID, etc.)
		expected_distance = getattr(qdrant_models.Distance, settings.VECTORSTORE_DISTANCE.upper(), qdrant_models.Distance.COSINE)
		if configured_distance != expected_distance:
			raise ValueError(
				f"Existing collection '{self.collection_name}' uses distance {configured_distance}, "
				f"expected {settings.VECTORSTORE_DISTANCE.lower()} distance."
			)

	def _ensure_payload_indexes(self) -> None:
		"""
		Create payload indexes for fast filtering (e.g. filter by channel, author).
		Skips fields that are already indexed.
		"""
		collection_info = self.client.get_collection(self.collection_name)
		existing_schema = set(collection_info.payload_schema.keys())
		for field_name, field_schema in self.payload_indexes.items():
			if field_name in existing_schema:
				continue  # Already indexed, skip
			self.client.create_payload_index(
				collection_name=self.collection_name,
				field_name=field_name,
				field_schema=field_schema,
				wait=True,
			)

	# ── Serialization Helpers ────────────────────────────────────────────

	@staticmethod
	def _serialize_value(value: Any) -> Any:
		"""
		Recursively convert Python objects to JSON-friendly types for Qdrant.
		Example: datetime → ISO string, nested dicts/lists are handled recursively.
		"""
		if isinstance(value, datetime):
			return value.isoformat()
		if isinstance(value, dict):
			return {k: QdrantVectorStore._serialize_value(v) for k, v in value.items()}
		if isinstance(value, list):
			return [QdrantVectorStore._serialize_value(v) for v in value]
		return value

	# ── Document ↔ Payload Conversion ────────────────────────────────────

	@staticmethod
	def document_to_payload(document: BaseSchema, schema_version: Optional[Type[BaseSchema]] = None) -> Dict[str, Any]:
		"""
		Convert a Document model → flat dict (Qdrant payload) for storage.

		The payload contains:
		  - All metadata fields (channel, author, timestamp, attributes)
		  - The text content (stored as both "text" and "document" for backward compat)
		  - _schema_version tag (e.g. "v2") so we know which schema to use when loading
		  - embedding_model and embedding_dim (if available on the document)

		Does NOT mutate the original document.
		"""
		# Dump metadata to dict and serialize dates/nested objects
		meta_dict = document.metadata.model_dump()
		payload: Dict[str, Any] = QdrantVectorStore._serialize_value(meta_dict.copy())

		# Store the text content
		payload["text"] = document.text
		payload.setdefault("document", document.text)  # backward compat with older payloads

		# Tag with schema version so we can reconstruct the right class later
		version = schema_version or document.metadata.schema_version
		payload["_schema_version"] = version._version_tag

		# Include embedding info if the document has it (SchemaV2+)
		if not payload.get("embedding_model"):
			payload["embedding_model"] = getattr(document, "embedding_model", None)
		if not payload.get("embedding_dim"):
			payload["embedding_dim"] = getattr(document, "embedding_dim", None)

		return payload

	@staticmethod
	def payload_to_document(point_id: Union[str, int], payload: Dict[str, Any]) -> BaseSchema:
		"""
		Convert a Qdrant payload dict → Document model.

		Uses _schema_version from the payload to pick the correct schema class
		(e.g. SchemaV1, SchemaV2). This lets old and new documents coexist.

		Any extra fields that the schema class accepts (like embedding_model)
		are automatically populated from the payload.
		"""
		# Read version tag; fall back to current config version if not stored
		version_tag = payload.get("_schema_version", settings.CURRENT_SCHEMA_VERSION)
		schema_cls = get_document_class(version_tag)

		# Rebuild the metadata object
		meta = DocumentMetadata(
			channel=payload.get("channel"),
			author=payload.get("author"),
			timestamp=payload.get("timestamp"),
			attributes=payload.get("attributes", {}),
			schema_version=version_tag,
		)

		# Start with the base fields every schema has
		kwargs: Dict[str, Any] = {
			"id": str(point_id),
			"text": payload.get("text") or payload.get("document", ""),
			"metadata": meta,
		}

		# Dynamically add any extra fields this schema version defines
		# (e.g. SchemaV2 has embedding_model and embedding_dim)
		for field_name in schema_cls.model_fields:
			if field_name not in kwargs and field_name in payload:
				kwargs[field_name] = payload[field_name]

		return schema_cls(**kwargs)

	# ── Input Validation ─────────────────────────────────────────────────

	@staticmethod
	def _validate_and_prepare_documents(
		documents: Sequence[str],
		metadatas: Optional[Sequence[Dict[str, Any]]],
		ids: Optional[Sequence[Union[str, int]]]
	) -> tuple[list[str], list[Dict[str, Any]], Optional[list[str]]]:
		"""
		Validate inputs before upload:
		  - documents must be non-empty strings
		  - ids (if given) must match document count, be unique, and non-empty
		  - metadatas (if given) must match document count
		Returns cleaned (texts, payloads, string_ids) ready for upload.
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

		# Convert all IDs to strings and check for duplicates
		if ids is not None:
			str_ids = [str(id_) for id_ in ids]
			if any(id_ is None or id_ == "" for id_ in str_ids):
				raise ValueError("All 'ids' must be non-empty when provided.")
			if len(set(str_ids)) != len(str_ids):
				raise ValueError("Duplicate IDs detected in 'ids'.")
		else:
			str_ids = None

		# Copy metadatas to avoid mutating caller's dicts
		payloads = [metadata.copy() for metadata in metadatas] if metadatas is not None else [{} for _ in documents]

		return list(documents), payloads, str_ids if ids is not None else None

	# ── Upload Helpers ───────────────────────────────────────────────────

	def _resolve_upload_options(self, options: Optional[VectorStoreUploadOptions]) -> VectorStoreUploadOptions:
		"""
		Merge caller-provided options with store defaults.
		If no options given, creates defaults from this store's config.
		"""
		if options is None:
			return VectorStoreUploadOptions(
				batch_size=self.batch_size,
				max_retries=self.max_retries,
			)
		# Fill in any None values with store defaults
		return VectorStoreUploadOptions(
			schema_version=options.schema_version,
			wait=options.wait,
			batch_size=options.batch_size if options.batch_size is not None else self.batch_size,
			parallel=options.parallel,
			max_retries=options.max_retries if options.max_retries is not None else self.max_retries,
			update_mode=options.update_mode,
		)

	def _build_serialized_payloads(
		self,
		texts: Sequence[str],
		payloads: Sequence[Dict[str, Any]],
		schema_version: Type[BaseSchema],
	) -> list[Dict[str, Any]]:
		"""
		Prepare payloads for Qdrant upload by adding:
		  - text and document fields (the actual content)
		  - embedding_model and embedding_dim (which model created these vectors)
		  - _schema_version tag

		Copies each payload to avoid mutating the originals.
		"""
		serialized_payloads = []
		for payload, doc in zip(payloads, texts):
			entry = payload.copy()  # Don't mutate the original
			entry["text"] = doc
			entry.setdefault("document", doc)  # backward compat
			entry.setdefault("embedding_model", self.doc_embedder.model)
			entry.setdefault("embedding_dim", self.doc_embedder.output_dimensionality)
			entry["_schema_version"] = schema_version._version_tag
			serialized_payloads.append(self._serialize_value(entry))
		return serialized_payloads

	# ── Public API: Adding Documents ─────────────────────────────────────

	def add_documents(
		self,
		documents: Sequence[str],
		metadatas: Optional[Sequence[Dict[str, Any]]] = None,
		ids: Optional[Sequence[Union[str, int]]] = None,
		options: Optional[VectorStoreUploadOptions] = None,
	) -> None:
		"""
		Add raw text strings to Qdrant.

		Steps:
		  1. Validate inputs (lengths match, no empty strings, no duplicate IDs)
		  2. Embed all texts into vectors via the embedding service
		  3. Build serialized payloads with metadata
		  4. Upload vectors + payloads to Qdrant
		"""
		try:
			resolved_options = self._resolve_upload_options(options)
			texts, payloads, ids = self._validate_and_prepare_documents(documents, metadatas, ids)
			vectors = self.doc_embedder.embed_texts(texts)
			serialized_payloads = self._build_serialized_payloads(
				texts,
				payloads,
				resolved_options.schema_version,
			)
			self.client.upload_collection(
				collection_name=self.collection_name,
				vectors=vectors,
				payload=serialized_payloads,
				ids=ids,
				batch_size=resolved_options.batch_size,
				parallel=resolved_options.parallel,
				max_retries=resolved_options.max_retries,
				wait=resolved_options.wait,
				update_mode=resolved_options.update_mode,
			)
		except Exception as e:
			logging.error(f"Failed to add documents to Qdrant: {e}")
			raise

	def add_document_models(
		self,
		documents: Sequence[BaseSchema],
		options: Optional[VectorStoreUploadOptions] = None,
	) -> None:
		"""
		Add Document model objects to Qdrant.
		Extracts text, metadata, and IDs from each model, then delegates to add_documents().
		"""
		if not documents:
			raise ValueError("'documents' must be a non-empty sequence of Document models.")
		resolved_options = self._resolve_upload_options(options)
		texts = [doc.text for doc in documents]
		payloads = [self.document_to_payload(doc, schema_version=resolved_options.schema_version) for doc in documents]
		ids = [doc.id for doc in documents]
		self.add_documents(
			texts,
			metadatas=payloads,
			ids=ids,
			options=resolved_options,
		)

	# ── Public API: Searching ────────────────────────────────────────────

	def similarity_search(self, query: str, n_results: int = 5, where: Optional[Dict[str, Any]] = None):
		"""
		Find the most similar documents to a query string.

		Args:
		  query:     the search text (gets embedded using the query embedding service)
		  n_results: how many results to return (default 5)
		  where:     optional metadata filter (e.g. {"channel": "general"})

		Returns a list of Qdrant ScoredPoint objects.
		"""
		try:
			if not query or not isinstance(query, str):
				raise ValueError("Query must be a non-empty string.")

			# Embed the query using the query-optimized embedding service
			q_vec = self.query_embedder.embed_text(query)

			# Build optional metadata filter
			filter_ = None
			if where:
				filter_ = qdrant_models.Filter(must=[
					qdrant_models.FieldCondition(
						key=k,
						match=qdrant_models.MatchValue(value=v)
					) for k, v in where.items()
				])

			# Run the search against Qdrant
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
