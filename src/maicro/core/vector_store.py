from functools import lru_cache
from pathlib import Path

from langchain_qdrant import QdrantVectorStore
from maicro.core.config import settings
from maicro.core.llm_provider import get_embeddings


@lru_cache(maxsize=1)
def get_vector_store():
    # Keep local persistence for MVP without requiring an external Qdrant server.
    path = Path(settings.QDRANT_PATH)
    path.mkdir(parents=True, exist_ok=True)

    return QdrantVectorStore.from_existing_collection(
        collection_name=settings.COLLECTION_NAME,
        embedding=get_embeddings(),
        path=str(path),
    )
