import asyncio
from types import SimpleNamespace

import httpx
from langchain_core.documents import Document
from qdrant_client.http.exceptions import UnexpectedResponse

from maicro.core import ingestion
from maicro.core.discord_fetcher import DiscordFetchError


def test_docs_from_discord_messages_skips_blank_content_and_appends_embeds():
    messages = [
        {"id": "ignored", "content": "   "},
        {
            "id": "42",
            "content": "Standup in 10 minutes",
            "author": {"username": "alice"},
            "timestamp": "2026-03-10T08:30:00+00:00",
            "embeds": [{"title": "Agenda", "description": "Sprint review"}],
        },
    ]

    docs = ingestion._docs_from_discord_messages(messages, channel_id="chan-1")

    assert len(docs) == 1
    assert docs[0].page_content == "[alice] Standup in 10 minutes\nAgenda\nSprint review"
    assert docs[0].metadata == {
        "source": "discord",
        "channel_id": "chan-1",
        "message_id": "42",
        "author": "alice",
        "timestamp": "2026-03-10T08:30:00+00:00",
    }


def test_ingest_documents_bootstraps_missing_collection(monkeypatch):
    documents = [Document(page_content="Release planning", metadata={"source": "json_file"})]
    bootstrapped = {}

    class FakeClient:
        def collection_exists(self, name: str) -> bool:
            return False  # Simulate missing collection

    class BrokenVectorStore:
        def add_documents(self, _documents):
            raise RuntimeError("Collection microclub_knowledge not found")

    class WorkingVectorStore:
        def __init__(self):
            self.added = []

        def add_documents(self, new_documents):
            self.added.extend(new_documents)

    working_store = WorkingVectorStore()

    class VectorStoreGetter:
        def __init__(self):
            self.calls = 0
            self.cache_clears = 0

        def __call__(self):
            self.calls += 1
            if self.calls == 1:
                return BrokenVectorStore()
            return working_store

        def cache_clear(self):
            self.cache_clears += 1

    getter = VectorStoreGetter()

    monkeypatch.setattr(ingestion, "get_qdrant_client", lambda: FakeClient())
    monkeypatch.setattr(ingestion, "get_vector_store", getter)
    monkeypatch.setattr(
        ingestion,
        "get_embeddings",
        lambda: SimpleNamespace(embed_query=lambda _query: [0.1, 0.2, 0.3, 0.4]),
    )
    monkeypatch.setattr(
        ingestion,
        "_ensure_collection_exists",
        lambda vector_size: bootstrapped.setdefault("vector_size", vector_size),
    )

    count = ingestion.ingest_documents(documents)

    assert count == 1
    assert bootstrapped["vector_size"] == 4
    assert getter.cache_clears == 2  # cache cleared twice: once for index check, once after bootstrap
    assert working_store.added == documents


def test_ingest_documents_bootstraps_missing_collection_when_qdrant_returns_404(monkeypatch):
    documents = [Document(page_content="Release planning", metadata={"source": "json_file"})]
    bootstrapped = {}

    class FakeClient:
        def collection_exists(self, name: str) -> bool:
            return False  # Simulate missing collection

    class BrokenVectorStore:
        def add_documents(self, _documents):
            raise UnexpectedResponse(
                status_code=404,
                reason_phrase="Not Found",
                content=b'{"status":{"error":"Not found: Collection `microclub_knowledge` doesn\\\'t exist!"}}',
                headers=httpx.Headers(),
            )

    class WorkingVectorStore:
        def __init__(self):
            self.added = []

        def add_documents(self, new_documents):
            self.added.extend(new_documents)

    working_store = WorkingVectorStore()

    class VectorStoreGetter:
        def __init__(self):
            self.calls = 0
            self.cache_clears = 0

        def __call__(self):
            self.calls += 1
            if self.calls == 1:
                return BrokenVectorStore()
            return working_store

        def cache_clear(self):
            self.cache_clears += 1

    getter = VectorStoreGetter()

    monkeypatch.setattr(ingestion, "get_qdrant_client", lambda: FakeClient())
    monkeypatch.setattr(ingestion, "get_vector_store", getter)
    monkeypatch.setattr(
        ingestion,
        "get_embeddings",
        lambda: SimpleNamespace(embed_query=lambda _query: [0.1, 0.2, 0.3, 0.4]),
    )
    monkeypatch.setattr(
        ingestion,
        "_ensure_collection_exists",
        lambda vector_size: bootstrapped.setdefault("vector_size", vector_size),
    )

    count = ingestion.ingest_documents(documents)

    assert count == 1
    assert bootstrapped["vector_size"] == 4
    assert getter.cache_clears == 2  # cache cleared twice: once for index check, once after bootstrap
    assert working_store.added == documents


def test_ingest_documents_ignores_missing_collection_during_duplicate_check(monkeypatch):
    documents = [
        Document(
            page_content="Release planning",
            metadata={"source": "discord", "channel_id": "chan-1", "message_id": "m1"},
        )
    ]
    bootstrapped = {}

    class FakeClient:
        def collection_exists(self, name: str) -> bool:
            return False  # Simulate missing collection
            
        def count(self, **_kwargs):
            raise UnexpectedResponse(
                status_code=404,
                reason_phrase="Not Found",
                content=b'{"status":{"error":"Not found: Collection `microclub_knowledge` doesn\\\'t exist!"}}',
                headers=httpx.Headers(),
            )

    class BrokenVectorStore:
        def add_documents(self, _documents):
            raise RuntimeError("Collection microclub_knowledge not found")

    class WorkingVectorStore:
        def __init__(self):
            self.added = []

        def add_documents(self, new_documents):
            self.added.extend(new_documents)

    working_store = WorkingVectorStore()

    class VectorStoreGetter:
        def __init__(self):
            self.calls = 0
            self.cache_clears = 0

        def __call__(self):
            self.calls += 1
            if self.calls == 1:
                return BrokenVectorStore()
            return working_store

        def cache_clear(self):
            self.cache_clears += 1

    getter = VectorStoreGetter()

    monkeypatch.setattr(ingestion, "get_qdrant_client", lambda: FakeClient())
    monkeypatch.setattr(ingestion, "get_vector_store", getter)
    monkeypatch.setattr(
        ingestion,
        "get_embeddings",
        lambda: SimpleNamespace(embed_query=lambda _query: [0.1, 0.2, 0.3, 0.4]),
    )
    monkeypatch.setattr(
        ingestion,
        "_ensure_collection_exists",
        lambda vector_size: bootstrapped.setdefault("vector_size", vector_size),
    )

    count = ingestion.ingest_documents(documents)

    assert count == 1
    assert bootstrapped["vector_size"] == 4
    assert getter.cache_clears == 2  # cache cleared twice: once for index check, once after bootstrap
    assert working_store.added == documents


def test_ingest_from_discord_collects_successes_and_permission_errors(monkeypatch):
    monkeypatch.setattr(ingestion.settings, "DISCORD_BOT_TOKEN", "discord-token")
    monkeypatch.setattr(ingestion.settings, "DISCORD_CHANNEL_IDS", "denied,open")

    # Simulate first run: no prior cursor for any channel
    monkeypatch.setattr(ingestion, "get_last_ingested_message_id", lambda channel_id: None)
    monkeypatch.setattr(ingestion, "update_last_ingested_message_id", lambda channel_id, msg_id: None)

    async def fake_fetch_channel_messages(
        bot_token: str,
        channel_id: str,
        limit=None,
        after=None,
    ):
        assert bot_token == "discord-token"
        assert limit is None   # bootstrap always passes limit=None now
        assert after is None   # no cursor on first run
        if channel_id == "denied":
            raise DiscordFetchError(channel_id=channel_id, status_code=403, message="forbidden")
        return [
            {
                "id": "m1",
                "content": "Shipping update",
                "author": {"username": "bob"},
                "timestamp": "2026-03-10T09:00:00+00:00",
            }
        ]

    monkeypatch.setattr(ingestion, "fetch_channel_messages", fake_fetch_channel_messages)
    monkeypatch.setattr(ingestion, "ingest_documents", lambda docs: len(docs))

    result = asyncio.run(ingestion.ingest_from_discord())

    assert result["channels"] == {"open": 1}
    assert "Missing access to channel" in result["errors"]["denied"]
    assert result["total_documents"] == 1
