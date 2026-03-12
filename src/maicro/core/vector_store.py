import atexit
from functools import lru_cache

from qdrant_client import QdrantClient
from qdrant_client.http import models as qdrant_models
from langchain_qdrant import QdrantVectorStore
from maicro.core.config import settings
from maicro.core.llm_provider import get_embeddings


@lru_cache(maxsize=1)
def get_qdrant_client() -> QdrantClient:
    """Return a singleton Qdrant client for this process."""
    if settings.QDRANT_API_KEY:
        return QdrantClient(url=settings.QDRANT_URL, api_key=settings.QDRANT_API_KEY)
    return QdrantClient(url=settings.QDRANT_URL)


@lru_cache(maxsize=1)
def get_vector_store() -> QdrantVectorStore:
    """Return a vector store backed by the singleton Qdrant client."""
    return QdrantVectorStore(
        client=get_qdrant_client(),
        collection_name=settings.COLLECTION_NAME,
        embedding=get_embeddings(),
        distance=qdrant_models.Distance.COSINE,
        validate_collection_config=False,
    )


@atexit.register
def _close_qdrant_client_on_exit() -> None:
    """Best-effort close to avoid noisy interpreter-shutdown warnings."""
    try:
        get_qdrant_client().close()
    except Exception:
        pass
