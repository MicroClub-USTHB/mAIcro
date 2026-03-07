from functools import lru_cache

from app.core.vector_store import QdrantVectorStore
from app.services.ai import GeminiProvider
from app.services.query_service import QueryService


@lru_cache(maxsize=1)
def get_query_service() -> QueryService:
    vector_store = QdrantVectorStore()
    gemini_provider = GeminiProvider()
    return QueryService(
        vector_store=vector_store,
        gemini_provider=gemini_provider,
    )
