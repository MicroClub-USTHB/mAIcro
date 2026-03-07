from functools import lru_cache

from langchain_qdrant import QdrantVectorStore
from app.core.config import settings
from app.core.llm_provider import get_embeddings


@lru_cache(maxsize=1)
def get_vector_store():
    # Use local path for persistent storage instead of URL to avoid needing a server for MVP
    path = "local_qdrant"

    return QdrantVectorStore.from_existing_collection(
        collection_name=settings.COLLECTION_NAME,
        embedding=get_embeddings(),
        path=path
    )

