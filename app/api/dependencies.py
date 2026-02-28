from functools import lru_cache

from app.core.embeddings import EmbeddingService
from app.core.vector_store import InMemoryVectorStore
from app.services.ai import GeminiProvider
from app.services.query_service import QueryService


@lru_cache(maxsize=1)
def get_query_service() -> QueryService:
    
    vector_store = InMemoryVectorStore()
    embedding_service = EmbeddingService()
    gemini_provider = GeminiProvider()
    return QueryService(
        vector_store=vector_store,
        embedding_service=embedding_service,
        gemini_provider=gemini_provider,
    )
