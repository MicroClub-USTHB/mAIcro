"""
Ingestion pipeline — converts raw data into LangChain Documents
and pushes them into the Qdrant vector store.

Supports two sources:
  1. JSON file  (existing announcements.json format)
  2. Discord messages (from the discord_fetcher)
"""

import json
import os
from datetime import datetime

from langchain_core.documents import Document
from langchain_qdrant import QdrantVectorStore

from app.core.config import settings
from app.core.llm_provider import get_embeddings


# ---------------------------------------------------------------------------
# Document converters
# ---------------------------------------------------------------------------

def _docs_from_json_file(file_path: str) -> list[Document]:
    """Load documents from a JSON file with [{title, content, date}, ...]."""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Data file not found: {file_path}")

    with open(file_path, "r") as f:
        data = json.load(f)

    docs: list[Document] = []
    for item in data:
        content = f"{item['title']}\n{item['content']}"
        metadata = {
            "source": "json_file",
            "file": file_path,
            "date": item.get("date", ""),
            "title": item["title"],
        }
        docs.append(Document(page_content=content, metadata=metadata))
    return docs


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

        # Build a readable page_content
        page_content = f"[{author_name}] {content}"

        # Attach embeds text if present
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


# ---------------------------------------------------------------------------
# Ingestion entry points
# ---------------------------------------------------------------------------

def ingest_documents(documents: list[Document]) -> int:
    """
    Push a list of LangChain Documents into the Qdrant vector store.
    Returns the number of documents ingested.
    """
    if not documents:
        return 0

    QdrantVectorStore.from_documents(
        documents=documents,
        embedding=get_embeddings(),
        path="local_qdrant",
        collection_name=settings.COLLECTION_NAME,
    )
    return len(documents)


def ingest_from_json(file_path: str) -> int:
    """Ingest documents from a JSON file."""
    docs = _docs_from_json_file(file_path)
    return ingest_documents(docs)


async def ingest_from_discord() -> dict:
    """
    Fetch messages from all configured Discord channels and ingest them.
    Returns a summary dict with per-channel counts.
    """
    from app.core.discord_fetcher import DiscordFetchError, fetch_channel_messages

    if not settings.DISCORD_BOT_TOKEN:
        raise ValueError("DISCORD_BOT_TOKEN not set in environment.")
    if not settings.discord_channel_id_list:
        raise ValueError("DISCORD_CHANNEL_IDS not set in environment.")

    summary: dict[str, int] = {}
    errors: dict[str, str] = {}
    total = 0

    for channel_id in settings.discord_channel_id_list:
        try:
            messages = await fetch_channel_messages(
                bot_token=settings.DISCORD_BOT_TOKEN,
                channel_id=channel_id,
                limit=200,
            )
            docs = _docs_from_discord_messages(messages, channel_id)
            count = ingest_documents(docs)
            summary[channel_id] = count
            total += count
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
