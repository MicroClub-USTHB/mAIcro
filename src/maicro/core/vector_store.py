import atexit
import logging
from functools import lru_cache

from qdrant_client import QdrantClient
from qdrant_client.http import models as qdrant_models
from langchain_qdrant import QdrantVectorStore

from maicro.core.config import settings
from maicro.core.llm_provider import get_embeddings


logger = logging.getLogger(__name__)

# Flag to track if indexes have been ensured
_indexes_ensured = False


def _ensure_collection_with_indexes() -> None:
    """Ensure the Qdrant collection exists with proper indexes for filtering.
    
    This runs only once to avoid repeated API calls.
    If collection doesn't exist, creates it with proper vector config from embeddings.
    """
    global _indexes_ensured
    if _indexes_ensured:
        return
    
    client = get_qdrant_client()
    collection_name = settings.COLLECTION_NAME

    # Check if collection exists
    try:
        collections = client.get_collections().collections
        collection_exists = any(c.name == collection_name for c in collections)
    except Exception:
        collection_exists = False

    if not collection_exists:
        # Get embedding size and create collection properly
        try:
            embedding = get_embeddings()
            # Get the actual vector size from the embedding model
            test_vector = embedding.embed_query("test")
            vector_size = len(test_vector)
            
            client.create_collection(
                collection_name=collection_name,
                vectors_config=qdrant_models.VectorParams(
                    size=vector_size,
                    distance=qdrant_models.Distance.COSINE,
                ),
            )
            logger.info(f"Created collection {collection_name} with vector size {vector_size}")
        except Exception as e:
            logger.warning(f"Could not create collection: {e}")
            # Let LangChain's QdrantVectorStore handle it
            _indexes_ensured = True
            return

    # Ensure payload indexes are created
    for field_name in ["metadata.channel_id", "metadata.message_id", "metadata.source"]:
        try:
            logger.info(f"Creating index on {field_name}")
            client.create_payload_index(
                collection_name=collection_name,
                field_name=field_name,
                field_schema=qdrant_models.PayloadSchemaType.KEYWORD,
            )
        except Exception as e:
            logger.debug(f"Index creation for {field_name}: {e}")
    
    # Enable Full-Text Index on page_content for keyword/BM25 search (hybrid search)
    try:
        logger.info("Creating full-text index on page_content")
        client.create_payload_index(
            collection_name=collection_name,
            field_name="page_content",
            field_schema=qdrant_models.TextIndexParams(
                type=qdrant_models.TextIndexType.TEXT,
                tokenizer=qdrant_models.TokenizerType.WORD,
                min_token_len=2,
                max_token_len=None,
                lowercase=True,
            ),
        )
    except Exception as e:
        logger.warning(f"Full-text index creation for page_content: {e}")
    
    _indexes_ensured = True


@lru_cache(maxsize=1)
def get_qdrant_client() -> QdrantClient:
    """Return a singleton Qdrant client for this process.

    Now strictly Cloud-only: requires QDRANT_URL and QDRANT_API_KEY.
    """
    if not settings.QDRANT_URL or not settings.QDRANT_API_KEY:
        raise ValueError(
            "mAIcro is now Cloud-only. Please set QDRANT_URL and QDRANT_API_KEY in your .env file. "
            "See README.md for instructions on setting up a free Qdrant Cloud cluster."
        )
    return QdrantClient(url=settings.QDRANT_URL, api_key=settings.QDRANT_API_KEY)


@lru_cache(maxsize=1)
def get_vector_store() -> QdrantVectorStore:
    """Return a vector store backed by the singleton Qdrant client."""
    client = get_qdrant_client()
    collection_name = settings.COLLECTION_NAME
    
    # Debug: Get collection info to understand the vector config
    try:
        collection_info = client.get_collection(collection_name)
        logger.info(f"Collection {collection_name} vectors: {collection_info.vectors_config}")
    except Exception as e:
        logger.warning(f"Could not get collection info: {e}")

    # Ensure collection exists with proper indexes before creating vector store
    _ensure_collection_with_indexes()

    return QdrantVectorStore(
        client=client,
        collection_name=collection_name,
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


# Import hybrid search functions from separate module
from maicro.core.hybrid_search import (
    hybrid_search,
    get_hybrid_retriever,
    _reciprocal_rank_fusion,
)

__all__ = ["hybrid_search", "get_hybrid_retriever"]
