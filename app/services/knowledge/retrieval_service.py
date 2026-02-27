"""
Knowledge retrieval service for community data.
Wraps the Chroma vector store and exposes simple add/search methods.
"""

from app.core.vector_store import ChromaVectorStore

class KnowledgeRetrievalService:
    def __init__(self):
        self.vector_store = ChromaVectorStore()

    def add_knowledge(self, chunks, metadatas=None, ids=None):
        """
        Add new knowledge chunks to the vector store.
        chunks: list of strings (text chunks)
        metadatas: list of dicts (optional)
        ids: list of unique ids (optional)
        """
        self.vector_store.add_documents(chunks, metadatas=metadatas, ids=ids)

    def search_knowledge(self, query, n_results=5, where=None):
        """
        Retrieve the most relevant knowledge chunks for a user query.
        query: string (user question)
        n_results: int (number of results to return)
        where: dict (optional metadata filter)
        Returns: Chroma query results dict
        """
        return self.vector_store.similarity_search(query, n_results=n_results, where=where)
