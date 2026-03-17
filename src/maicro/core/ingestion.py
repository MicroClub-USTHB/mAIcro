"""
Ingestion pipeline — converts raw data into LangChain Documents
and pushes them into the Qdrant vector store.

Supports one source:
  1. Discord messages (from the discord_fetcher)

For startup audit (offline edit/delete reconciliation), see `maicro.core.audit`.
"""

import logging

from langchain_core.documents import Document
from qdrant_client.http import models as qdrant_models
from qdrant_client.http.exceptions import UnexpectedResponse

from maicro.core.config import settings
from maicro.core.discord_fetcher import DiscordFetchError, fetch_channel_messages
from maicro.core.llm_provider import get_embeddings
from maicro.core.state import get_last_ingested_message_id, update_last_ingested_message_id
from maicro.core.vector_store import get_qdrant_client, get_vector_store

# Re-export run_startup_audit for backward compatibility
from maicro.core.audit import run_startup_audit

__all__ = ["ingest_documents", "ingest_from_discord", "run_startup_audit"]

logger = logging.getLogger(__name__)



def _is_missing_collection_error(message: str) -> bool:
    """Return True when an exception message indicates the Qdrant collection is missing."""
    if not message:
        return False
    lowered = message.lower()
    collection = settings.COLLECTION_NAME.lower()
    if collection not in lowered:
        return False
    return any(needle in lowered for needle in ("doesn't exist", "does not exist", "not found"))


def _is_missing_collection_exception(exc: Exception) -> bool:
    """Return True when an exception indicates the Qdrant collection is missing."""
    if isinstance(exc, UnexpectedResponse):
        if exc.status_code != 404:
            return False
        return _is_missing_collection_error(exc.content.decode("utf-8", errors="ignore"))
    return _is_missing_collection_error(str(exc))


def _bootstrap_collection() -> None:
    """Create the Qdrant collection (if missing) and clear vector-store cache."""
    embedding = get_embeddings()
    vector_size = len(embedding.embed_query("collection bootstrap"))
    _ensure_collection_exists(vector_size)
    get_vector_store.cache_clear()


def _docs_from_discord_messages(
    messages: list[dict],
    channel_id: str,
) -> list[Document]:
    """
    Convert raw Discord message dicts into LangChain Documents.
    Skips empty messages and bot commands.
    """
    docs: list[Document] = []
    for msg in messages:
        content = (msg.get("content") or "").strip()
        if not content:
            continue

        author = msg.get("author", {})
        author_name = author.get("username", "unknown")
        timestamp = msg.get("timestamp", "")

        page_content = f"[{author_name}] {content}"

        for embed in msg.get("embeds", []):
            if embed.get("title"):
                page_content += f"\n{embed['title']}"
            if embed.get("description"):
                page_content += f"\n{embed['description']}"

        metadata = {
            "source": "discord",
            "channel_id": channel_id,
            "message_id": msg.get("id", ""),
            "author": author_name,
            "timestamp": timestamp,
        }
        docs.append(Document(page_content=page_content, metadata=metadata))

    return docs



def _ensure_collection_exists(vector_size: int) -> None:
    """Create local collection if missing, without relying on cached vector store."""
    client = get_qdrant_client()
    if not client.collection_exists(settings.COLLECTION_NAME):
        client.create_collection(
            collection_name=settings.COLLECTION_NAME,
            vectors_config=qdrant_models.VectorParams(
                size=vector_size,
                distance=qdrant_models.Distance.COSINE,
            ),
        )


def ingest_documents(documents: list[Document], filter_duplicates: bool = True) -> int:
    """
    Push a list of LangChain Documents into the Qdrant vector store.
    Returns the number of documents ingested.
    
    Args:
        documents: List of LangChain Documents to ingest.
        filter_duplicates: If True, skip documents that already exist based on message_id.
    """
    if not documents:
        return 0

    if filter_duplicates:
        documents, duplicate_count = _filter_duplicate_documents(documents)
        if not documents:
            logger.debug("[ingestion] All documents were duplicates, nothing to ingest")
            return 0

    try:
        vector_store = get_vector_store()
        vector_store.add_documents(documents)
    except UnexpectedResponse as exc:
        if exc.status_code == 401:
            raise ValueError(
                "Qdrant unauthorized (401). Check QDRANT_URL and QDRANT_API_KEY in your .env."
            ) from exc
        if exc.status_code == 404 and _is_missing_collection_error(
            exc.content.decode("utf-8", errors="ignore")
        ):
            _bootstrap_collection()
            vector_store = get_vector_store()
            vector_store.add_documents(documents)
        else:
            raise
    except Exception as exc:
        # First-run behavior: create the collection automatically if missing.
        if _is_missing_collection_error(str(exc)):
            _bootstrap_collection()
            vector_store = get_vector_store()
            vector_store.add_documents(documents)
        else:
            raise
    return len(documents)



def _filter_by_message(channel_id: str, message_id: str) -> qdrant_models.Filter:
    """Build a Qdrant payload filter matching a specific (channel_id, message_id) pair."""
    return qdrant_models.Filter(
        must=[
            qdrant_models.FieldCondition(
                key="metadata.channel_id",
                match=qdrant_models.MatchValue(value=channel_id),
            ),
            qdrant_models.FieldCondition(
                key="metadata.message_id",
                match=qdrant_models.MatchValue(value=message_id),
            ),
        ]
    )


def _check_duplicate_message_ids(documents: list[Document]) -> set[str]:
    """
    Check which message IDs already exist in the vector store.
    Returns a set of message IDs that are already present.
    """
    client = get_qdrant_client()
    existing_ids: set[str] = set()

    channel_msg_ids: dict[str, list[str]] = {}
    for doc in documents:
        channel_id = doc.metadata.get("channel_id", "")
        message_id = doc.metadata.get("message_id", "")
        if channel_id and message_id:
            if channel_id not in channel_msg_ids:
                channel_msg_ids[channel_id] = []
            channel_msg_ids[channel_id].append(message_id)

    for channel_id, message_ids in channel_msg_ids.items():
        for msg_id in message_ids:
            try:
                count_result = client.count(
                    collection_name=settings.COLLECTION_NAME,
                    count_filter=_filter_by_message(channel_id, msg_id),
                    exact=True,
                )
            except Exception as exc:
                if _is_missing_collection_exception(exc):
                    return set()
                raise
            if count_result.count > 0:
                existing_ids.add(msg_id)

    return existing_ids


def _filter_duplicate_documents(documents: list[Document]) -> tuple[list[Document], int]:
    """
    Filter out documents that already exist in the vector store based on message_id.
    Returns a tuple of (filtered_documents, duplicate_count).
    """
    if not documents:
        return documents, 0

    existing_ids = _check_duplicate_message_ids(documents)
    if not existing_ids:
        return documents, 0

    filtered = []
    duplicate_count = 0
    for doc in documents:
        msg_id = doc.metadata.get("message_id", "")
        if msg_id in existing_ids:
            duplicate_count += 1
            logger.debug("[ingestion] Skipping duplicate message_id=%s", msg_id)
        else:
            filtered.append(doc)

    if duplicate_count > 0:
        logger.info("[ingestion] Filtered %d duplicate message(s)", duplicate_count)

    return filtered, duplicate_count


def delete_message_from_store(channel_id: str, message_id: str) -> int:
    """
    Remove all Qdrant points whose payload matches (channel_id, message_id).
    Returns the number of points deleted (0 if none existed).
    """
    client = get_qdrant_client()
    try:
        count_result = client.count(
            collection_name=settings.COLLECTION_NAME,
            count_filter=_filter_by_message(channel_id, message_id),
            exact=True,
        )
    except Exception as exc:
        if _is_missing_collection_exception(exc):
            return 0
        raise
    n = count_result.count
    if n:
        client.delete(
            collection_name=settings.COLLECTION_NAME,
            points_selector=qdrant_models.FilterSelector(
                filter=_filter_by_message(channel_id, message_id)
            ),
        )
        logger.debug(
            "[ingestion] deleted %d point(s) for message_id=%s channel=%s",
            n, message_id, channel_id,
        )
    return n


def update_message_in_store(message: dict, channel_id: str) -> int:
    """
    Update a message in the vector store:
    """
    message_id = message.get("id", "")
    delete_message_from_store(channel_id, message_id)
    docs = _docs_from_discord_messages([message], channel_id)
    if not docs:
        return 0
    return ingest_documents(docs)


async def ingest_from_discord(limit_per_channel: int = 200) -> dict:
    """
    Fetch messages from all configured Discord channels and ingest them.
    Returns a summary dict with per-channel counts.
    """
    if not settings.DISCORD_BOT_TOKEN:
        raise ValueError("DISCORD_BOT_TOKEN not set in environment.")
    if not settings.discord_channel_id_list:
        raise ValueError("DISCORD_CHANNEL_IDS not set in environment.")

    summary: dict[str, int] = {}
    errors: dict[str, str] = {}
    total = 0

    for channel_id in settings.discord_channel_id_list:
        try:
            last_message_id = get_last_ingested_message_id(channel_id)
            messages = await fetch_channel_messages(
                bot_token=settings.DISCORD_BOT_TOKEN,
                channel_id=channel_id,
                limit=None,
                after=last_message_id,
            )
            
            if not messages:
                summary[channel_id] = 0
                continue
                
            docs = _docs_from_discord_messages(messages, channel_id)
            count = ingest_documents(docs)
            summary[channel_id] = count
            total += count
            
           
            if messages:
                newest_message = messages[-1] if last_message_id else messages[0]
                update_last_ingested_message_id(channel_id, newest_message["id"])
                
        except DiscordFetchError as exc:
            if exc.status_code == 403:
                errors[channel_id] = (
                    "Missing access to channel. Ensure the bot is in the server and has "
                    "View Channel + Read Message History permissions."
                )
            elif exc.status_code == 401:
                errors[channel_id] = "Unauthorized bot token. Verify DISCORD_BOT_TOKEN."
            else:
                errors[channel_id] = exc.message
        except Exception as exc:
            errors[channel_id] = str(exc)

    return {
        "channels": summary,
        "errors": errors,
        "total_documents": total,
    }
