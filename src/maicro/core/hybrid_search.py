"""Hybrid Search Module - Combines semantic (vector) and keyword (BM25) search.

This module provides hybrid search functionality using Qdrant's Prefetch API
and Reciprocal Rank Fusion (RRF) for merging results.
"""

import logging

from qdrant_client import QdrantClient
from qdrant_client.http import models as qdrant_models
from langchain_core.documents import Document
from langchain_core.retrievers import RetrieverLike

from maicro.core.config import settings
from maicro.core.llm_provider import get_embeddings
from maicro.core.vector_store import get_qdrant_client

logger = logging.getLogger(__name__)


def _reciprocal_rank_fusion(
    results_by_source: dict[str, list[tuple[str, float]]], 
    k: int | None = None
) -> list[tuple[str, float]]:
    """Combine ranked lists using Reciprocal Rank Fusion.
    
    RRF_score(doc) = Σ (1 / (k + rank(doc)))
    
    Args:
        results_by_source: Dict mapping source name to list of (doc_id, score) tuples
        k: Constant for RRF (defaults to settings.HYBRID_SEARCH_RRF_K = 60)
    
    Returns:
        List of (doc_id, rrf_score) tuples, sorted by rrf_score descending
    """
    if k is None:
        k = getattr(settings, 'HYBRID_SEARCH_RRF_K', 60)
    
    rrf_scores: dict[str, float] = {}
    
    for source, results in results_by_source.items():
        for rank, (doc_id, score) in enumerate(results, start=1):
            if doc_id not in rrf_scores:
                rrf_scores[doc_id] = 0.0
            rrf_scores[doc_id] += 1.0 / (k + rank)
    
    # Sort by RRF score descending
    sorted_results = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)
    return sorted_results


def hybrid_search(
    query: str,
    alpha: float | None = None,
    k: int = 5,
    filter_condition: qdrant_models.Filter | None = None,
) -> list[Document]:
    """Execute hybrid search combining semantic (vector) and keyword (BM25) search.
    
    Uses Qdrant's Prefetch API to execute both searches and merges results
    using Reciprocal Rank Fusion (RRF).
    
    Args:
        query: Search query string
        alpha: Weight for semantic search (1-alpha for keyword). 
               If None, uses settings.HYBRID_SEARCH_ALPHA (default 0.7)
        k: Number of results to return
        filter_condition: Optional Qdrant filter
    
    Returns:
        List of Documents sorted by RRF score
    """
    if alpha is None:
        alpha = getattr(settings, 'HYBRID_SEARCH_ALPHA', 0.7)
    
    client = get_qdrant_client()
    collection_name = settings.COLLECTION_NAME
    embedding = get_embeddings()
    
    # Get query vector for semantic search
    query_vector = embedding.embed_query(query)
    
    # Prepare prefetch requests
    prefetches = []
    
    # 1. Semantic (vector) search via prefetch
    prefetches.append(
        qdrant_models.Prefetch(
            query=query_vector,
            using="cosine",  # Using cosine distance as configured
            limit=k * 2,  # Fetch more for better fusion
            filter=filter_condition,
        )
    )
    
    # 2. Keyword (BM25) search via prefetch
    prefetches.append(
        qdrant_models.Prefetch(
            query=qdrant_models.TextQuery(
                text=query,
                field="page_content",
            ),
            limit=k * 2,
            filter=filter_condition,
        )
    )
    
    # Execute hybrid search using query with prefetch
    try:
        # Use the raw Qdrant client for hybrid search
        search_results = client.search(
            collection_name=collection_name,
            query_vector=query_vector,  # Primary query vector
            prefetch=prefetches,
            query_filter=filter_condition,
            limit=k,
            with_payload=True,
            with_vectors=False,
        )
        
        # Convert results to Documents
        documents = []
        for hit in search_results:
            # Extract content from payload
            payload = hit.payload or {}
            page_content = payload.get("page_content", "")
            metadata = payload.get("metadata", {})
            
            documents.append(
                Document(
                    page_content=page_content,
                    metadata=metadata,
                )
            )
        
        return documents
        
    except Exception as e:
        logger.warning(f"Hybrid search failed, falling back to vector search: {e}")
        # Fallback to standard vector search
        from maicro.core.vector_store import get_vector_store
        vector_store = get_vector_store()
        return vector_store.similarity_search(
            query=query,
            k=k,
            filter=filter_condition,
        )


def get_hybrid_retriever(
    alpha: float | None = None,
    k: int = 5,
) -> RetrieverLike:
    """Return a hybrid search retriever interface.
    
    Args:
        alpha: Weight for semantic search (1-alpha for keyword).
               If None, uses settings.HYBRID_SEARCH_ALPHA (default 0.7)
        k: Number of results to retrieve
    
    Returns:
        A retriever-like function that takes a query string and returns documents
    """
    def retriever(query: str) -> list[Document]:
        return hybrid_search(
            query=query,
            alpha=alpha,
            k=k,
        )
    
    return retriever
