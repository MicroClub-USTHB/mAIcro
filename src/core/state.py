import logging
import uuid
from typing import Optional

from qdrant_client.http import models as qdrant_models

from core.config import settings
from core.vector_store import get_qdrant_client

logger = logging.getLogger(__name__)

# Use a deterministic namespace for cursor UUIDs
CURSOR_NAMESPACE = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")


def _get_cursor_id(channel_id: str) -> str:
    """Generate a deterministic UUID for a channel's cursor point."""
    return str(uuid.uuid5(CURSOR_NAMESPACE, f"cursor_{channel_id}"))


def get_last_ingested_message_id(channel_id: str) -> Optional[str]:
    """Get the last ingested message ID from Qdrant Cloud."""
    client = get_qdrant_client()
    point_id = _get_cursor_id(channel_id)

    try:
        results = client.retrieve(
            collection_name=settings.COLLECTION_NAME,
            ids=[point_id],
            with_payload=True,
            with_vectors=False,
        )
        if results:
            return results[0].payload.get("message_id")
    except Exception as e:
        logger.debug(f"[state] Failed to retrieve cursor for {channel_id}: {e}")

    return None


def ensure_channel_in_state(channel_id: str) -> None:
    """Ensures channel exists (No-op in Qdrant implementation)."""
    pass


def update_last_ingested_message_id(channel_id: str, message_id: str) -> None:
    """Update or create the last ingested message ID in Qdrant Cloud."""
    client = get_qdrant_client()
    point_id = _get_cursor_id(channel_id)

    # We store cursors as special points with no vectors (or zero vectors)
    # and a 'source=ingestion_cursor' tag to easily filter them out if needed.
    client.upsert(
        collection_name=settings.COLLECTION_NAME,
        points=[
            qdrant_models.PointStruct(
                id=point_id,
                vector={},  # Empty dict for collections with named vectors?
                # For our standard COSINE collection, we might need a dummy vector
                # or just use payload.
                payload={
                    "metadata": {
                        "channel_id": channel_id,
                        "source": "ingestion_cursor",
                    },
                    "message_id": message_id,
                    "page_content": f"Ingestion cursor for channel {channel_id}",
                },
            )
        ],
    )
    logger.debug(f"[state] Updated cursor for {channel_id} to {message_id}")
