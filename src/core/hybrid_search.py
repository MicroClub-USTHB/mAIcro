"""Hybrid Search Module - Combines semantic (vector) and keyword (BM25) search.

This module provides hybrid search functionality using Qdrant's Prefetch API
and Reciprocal Rank Fusion (RRF) for merging results.
"""

import logging

from qdrant_client.http import models as qdrant_models
from langchain_core.documents import Document
from langchain_core.retrievers import RetrieverLike

from core.config import settings
from core.llm_provider import get_embeddings


def _get_qdrant_client():
    from core.vector_store import get_qdrant_client

    return get_qdrant_client()


logger = logging.getLogger(__name__)


def _reciprocal_rank_fusion(
    results_by_source: dict[str, list[tuple[str, float]]], k: int | None = None
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
        k = getattr(settings, "HYBRID_SEARCH_RRF_K", 60)

    rrf_scores: dict[str, float] = {}

    for source, results in results_by_source.items():
        for rank, (doc_id, score) in enumerate(results, start=1):
            if doc_id not in rrf_scores:
                rrf_scores[doc_id] = 0.0
            rrf_scores[doc_id] += 1.0 / (k + rank)

    # Sort by RRF score descending
    sorted_results = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)
    return sorted_results


def _is_message_id(query: str) -> bool:
    """Check if query looks like a Discord message ID (numeric string)."""
    return query.isdigit() and len(query) >= 17


def hybrid_search(
    query: str,
    alpha: float | None = None,
    k: int = 5,
    filter_condition: qdrant_models.Filter | None = None,
) -> list[Document]:
    """Execute hybrid search combining semantic (vector) and keyword (BM25) search.


    Returns:
        List of Documents sorted by RRF score
    """
    if alpha is None:
        alpha = getattr(settings, "HYBRID_SEARCH_ALPHA", 0.7)

    client = _get_qdrant_client()
    collection_name = settings.COLLECTION_NAME
    embedding = get_embeddings()

    query_vector = embedding.embed_query(query)

    vector_results = client.query_points(
        collection_name=collection_name,
        query=query_vector,
        query_filter=filter_condition,
        limit=k * 2,
        with_payload=True,
        with_vectors=False,
    )

    text_match_condition = qdrant_models.FieldCondition(
        key="page_content",
        match=qdrant_models.MatchText(text=query),
    )

    if filter_condition:
        text_filter = qdrant_models.Filter(
            must=[filter_condition, text_match_condition]
        )
    else:
        text_filter = qdrant_models.Filter(must=[text_match_condition])

    text_results = client.scroll(
        collection_name=collection_name,
        scroll_filter=text_filter,
        limit=k * 2,
        with_payload=True,
        with_vectors=False,
    )

    message_id_docs = []
    if _is_message_id(query):
        message_id_condition = qdrant_models.FieldCondition(
            key="metadata.message_id",
            match=qdrant_models.MatchValue(value=query),
        )

        if filter_condition:
            message_id_filter = qdrant_models.Filter(
                must=[filter_condition, message_id_condition]
            )
        else:
            message_id_filter = qdrant_models.Filter(must=[message_id_condition])

        message_id_results = client.scroll(
            collection_name=collection_name,
            scroll_filter=message_id_filter,
            limit=k * 2,
            with_payload=True,
            with_vectors=False,
        )

        for hit in message_id_results[0]:
            payload = hit.payload or {}
            doc_id = hit.id
            score = 2.0
            message_id_docs.append((doc_id, score, payload))

    vector_docs = []
    for hit in vector_results.points:
        payload = hit.payload or {}
        doc_id = hit.id
        score = hit.score if hasattr(hit, "score") else 1.0
        vector_docs.append((doc_id, score, payload))

    text_docs = []
    for hit in text_results[0]:
        payload = hit.payload or {}
        doc_id = hit.id
        score = 1.0
        text_docs.append((doc_id, score, payload))

    rrf_k = getattr(settings, "HYBRID_SEARCH_RRF_K", 60)

    results_by_source = {}

    vector_ranked = [(doc_id, score) for doc_id, score, _ in vector_docs]
    results_by_source["vector"] = vector_ranked

    text_ranked = [(doc_id, 1.0) for doc_id, _, _ in text_docs]
    results_by_source["text"] = text_ranked

    if message_id_docs:
        message_id_ranked = [(doc_id, score) for doc_id, score, _ in message_id_docs]
        results_by_source["message_id"] = message_id_ranked

    rrf_scores = _reciprocal_rank_fusion(results_by_source, k=rrf_k)

    doc_map = {}
    for doc_id, score, payload in vector_docs:
        doc_map[doc_id] = payload
    for doc_id, score, payload in text_docs:
        if doc_id not in doc_map:
            doc_map[doc_id] = payload
    for doc_id, score, payload in message_id_docs:
        if doc_id not in doc_map:
            doc_map[doc_id] = payload

    documents = []
    for doc_id, rrf_score in rrf_scores:
        if doc_id in doc_map:
            payload = doc_map[doc_id]
            page_content = payload.get("page_content", "")
            metadata = payload.get("metadata", {})
            documents.append(
                Document(
                    page_content=page_content,
                    metadata=metadata,
                )
            )

    return documents[:k]


class _HybridRetriever:
    """Wrapper class to make hybrid search compatible with LangChain's retriever interface."""

    def __init__(self, alpha: float | None = None, k: int = 5):
        self.alpha = alpha
        self.k = k

    def invoke(self, query: str) -> list[Document]:
        return hybrid_search(
            query=query,
            alpha=self.alpha,
            k=self.k,
        )

    def __call__(self, query: str) -> list[Document]:
        return self.invoke(query)


def get_hybrid_retriever(
    alpha: float | None = None,
    k: int = 5,
) -> RetrieverLike:
    """Return a hybrid search retriever interface.


    Returns:
        A retriever with .invoke() method
    """
    return _HybridRetriever(alpha=alpha, k=k)
