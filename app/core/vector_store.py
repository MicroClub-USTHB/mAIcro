
import chromadb
from app.core.config import settings
from app.core.embeddings import get_document_embedding_service, get_query_embedding_service

import logging

class ChromaVectorStore:
	def __init__(self):
		self.client = chromadb.PersistentClient(path=settings.VECTORSTORE_PATH)
		self.collection = self.client.get_or_create_collection(settings.VECTORSTORE_COLLECTION)
		self.doc_embedder = get_document_embedding_service()
		self.query_embedder = get_query_embedding_service()

	def add_documents(self, documents, metadatas=None, ids=None):
		"""Embed and add documents to the Chroma collection, with validation and error handling."""
		try:
			if not documents or not isinstance(documents, list):
				raise ValueError("'documents' must be a non-empty list of strings.")
			n = len(documents)
			if ids is not None and len(ids) != n:
				raise ValueError("'ids' must be the same length as 'documents'.")
			if metadatas is not None and len(metadatas) != n:
				raise ValueError("'metadatas' must be the same length as 'documents'.")
			if any(not doc or not isinstance(doc, str) for doc in documents):
				raise ValueError("All documents must be non-empty strings.")
			if ids is not None and len(set(ids)) != len(ids):
				raise ValueError("Duplicate IDs detected in 'ids'.")

			vectors = self.doc_embedder.embed_texts(documents)
			self.collection.add(
				documents=documents,
				embeddings=vectors,
				metadatas=metadatas,
				ids=ids
			)
		except Exception as e:
			logging.error(f"Failed to add documents to Chroma: {e}")
			raise

	def similarity_search(self, query, n_results=5, where=None):
		"""Embed the query and return the most similar documents, with error handling."""
		try:
			if not query or not isinstance(query, str):
				raise ValueError("Query must be a non-empty string.")
			q_vec = self.query_embedder.embed_text(query)
			results = self.collection.query(
				query_embeddings=[q_vec],
				n_results=n_results,
				where=where
			)
			return results
		except Exception as e:
			logging.error(f"Similarity search failed: {e}")
			raise
