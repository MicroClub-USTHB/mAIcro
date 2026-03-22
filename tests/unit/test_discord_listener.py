"""
Unit tests for discord_listener.handle_message_create and handle_message_delete.

We test the dict-based handler in isolation — no real Discord connection or
Qdrant needed.  The discord.py import only happens inside run_discord_listener(),
so these tests work without discord.py installed.
"""

import asyncio
from unittest.mock import MagicMock


from core import discord_listener


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

WATCHED = {"111111111111111111", "222222222222222222"}

VALID_MESSAGE = {
    "id": "999",
    "channel_id": "111111111111111111",
    "content": "New sprint kick-off tomorrow at 10am",
    "author": {"username": "alice"},
    "timestamp": "2026-03-15T09:00:00+00:00",
    "embeds": [],
}


# ---------------------------------------------------------------------------
# handle_message_create — channel filtering
# ---------------------------------------------------------------------------


def test_handle_message_create_ignores_wrong_channel(monkeypatch):
    """Messages in unwatched channels must not trigger ingestion."""
    called = []
    monkeypatch.setattr(
        discord_listener, "ingest_documents", lambda docs: called.append(docs) or 0
    )

    asyncio.run(
        discord_listener.handle_message_create(
            {**VALID_MESSAGE, "channel_id": "999999999999999999"},
            WATCHED,
        )
    )

    assert called == [], "ingest_documents should not be called for unwatched channels"


def test_handle_message_create_ingests_and_updates_state(monkeypatch):
    """Valid message in a watched channel must be ingested and state updated."""
    ingested = []
    state_updates = []

    monkeypatch.setattr(
        discord_listener,
        "ingest_documents",
        lambda docs: ingested.extend(docs) or len(docs),
    )
    monkeypatch.setattr(
        discord_listener,
        "update_last_ingested_message_id",
        lambda channel_id, msg_id: state_updates.append((channel_id, msg_id)),
    )

    asyncio.run(discord_listener.handle_message_create(VALID_MESSAGE, WATCHED))

    assert len(ingested) == 1
    assert ingested[0].page_content == "[alice] New sprint kick-off tomorrow at 10am"
    assert state_updates == [("111111111111111111", "999")]


def test_handle_message_create_skips_blank_content(monkeypatch):
    """Empty message content must not produce any documents or state updates."""
    ingested = []
    state_updates = []

    monkeypatch.setattr(
        discord_listener,
        "ingest_documents",
        lambda docs: ingested.extend(docs) or len(docs),
    )
    monkeypatch.setattr(
        discord_listener,
        "update_last_ingested_message_id",
        lambda channel_id, msg_id: state_updates.append((channel_id, msg_id)),
    )

    asyncio.run(
        discord_listener.handle_message_create(
            {**VALID_MESSAGE, "content": "   "},
            WATCHED,
        )
    )

    assert ingested == []
    assert state_updates == []


def test_handle_message_create_handles_ingestion_error(monkeypatch, caplog):
    """Ingestion failures must not update cursor and should log the error."""
    import logging

    state_updates = []

    def fake_ingest(docs):
        raise RuntimeError("Qdrant connection timeout")

    def fake_update_cursor(channel_id, msg_id):
        state_updates.append((channel_id, msg_id))

    monkeypatch.setattr(discord_listener, "ingest_documents", fake_ingest)
    monkeypatch.setattr(
        discord_listener, "update_last_ingested_message_id", fake_update_cursor
    )

    with caplog.at_level(logging.ERROR, logger="core.discord_listener"):
        asyncio.run(discord_listener.handle_message_create(VALID_MESSAGE, WATCHED))

    assert state_updates == [], "Cursor must not be updated on ingestion failure"
    assert any("failed to ingest" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# _message_to_dict — shape contract
# ---------------------------------------------------------------------------


def test_message_to_dict_produces_expected_shape():
    """_message_to_dict must produce the same dict shape as the REST API returns."""
    from datetime import datetime, timezone

    # Build a minimal fake discord.Message-like object using MagicMock
    embed = MagicMock()
    embed.title = "Agenda"
    embed.description = "Sprint review"

    msg = MagicMock()
    msg.id = 123456789
    msg.channel.id = 111111111111111111
    msg.content = "Hello world"
    msg.author.name = "bob"
    msg.created_at = datetime(2026, 3, 15, 9, 0, 0, tzinfo=timezone.utc)
    msg.embeds = [embed]

    result = discord_listener._message_to_dict(msg)

    assert result == {
        "id": "123456789",
        "channel_id": "111111111111111111",
        "content": "Hello world",
        "author": {"username": "bob"},
        "timestamp": "2026-03-15T09:00:00+00:00",
        "embeds": [{"title": "Agenda", "description": "Sprint review"}],
    }


# ---------------------------------------------------------------------------
# run_discord_listener — guard clauses
# ---------------------------------------------------------------------------


def test_run_discord_listener_returns_early_without_token(caplog):
    """Missing token must log an error and return without connecting."""
    import logging

    with caplog.at_level(logging.ERROR, logger="core.discord_listener"):
        asyncio.run(discord_listener.run_discord_listener("", ["111"]))
    assert any("DISCORD_BOT_TOKEN" in r.message for r in caplog.records)


def test_run_discord_listener_returns_early_without_channels(caplog):
    """Missing channel list must log an error and return without connecting."""
    import logging

    with caplog.at_level(logging.ERROR, logger="core.discord_listener"):
        asyncio.run(discord_listener.run_discord_listener("some-token", []))
    assert any("No channel IDs" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# handle_message_delete — cursor handling
# ---------------------------------------------------------------------------


def test_handle_message_delete_removes_point(monkeypatch):
    """Deleting a message must remove the corresponding Qdrant point."""
    deleted = []

    def fake_delete(channel_id, message_id):
        deleted.append((channel_id, message_id))
        return 1

    monkeypatch.setattr(discord_listener, "delete_message_from_store", fake_delete)
    monkeypatch.setattr(
        discord_listener, "get_last_ingested_message_id", lambda ch: None
    )

    asyncio.run(
        discord_listener.handle_message_delete(
            {"channel_id": "111111111111111111", "id": "999"},
            WATCHED,
        )
    )

    assert deleted == [("111111111111111111", "999")]


def test_handle_message_delete_ignores_wrong_channel(monkeypatch):
    """Messages in unwatched channels must not trigger deletion."""
    called = []
    monkeypatch.setattr(
        discord_listener, "delete_message_from_store", lambda *a: called.append(a) or 0
    )

    asyncio.run(
        discord_listener.handle_message_delete(
            {"channel_id": "999999999999999999", "id": "999"},
            WATCHED,
        )
    )

    assert called == []


def test_handle_message_delete_updates_cursor_when_deleted_message_was_cursor(
    monkeypatch,
):
    """When the deleted message was the cursor, cursor must advance to most recent."""
    deleted = []
    cursor_updates = []
    fetched_messages = []

    def fake_delete(channel_id, message_id):
        deleted.append((channel_id, message_id))
        return 1

    def fake_get_cursor(channel_id):
        return "999"  # The message being deleted is the cursor

    def fake_update_cursor(channel_id, msg_id):
        cursor_updates.append((channel_id, msg_id))

    async def fake_fetch(bot_token, channel_id, limit):
        fetched_messages.append((bot_token, channel_id, limit))
        return [{"id": "1000", "content": "newest message"}]

    monkeypatch.setattr(discord_listener, "delete_message_from_store", fake_delete)
    monkeypatch.setattr(discord_listener, "get_last_ingested_message_id", fake_get_cursor)
    monkeypatch.setattr(
        discord_listener, "update_last_ingested_message_id", fake_update_cursor
    )
    monkeypatch.setattr(discord_listener, "fetch_channel_messages", fake_fetch)
    monkeypatch.setattr(discord_listener.settings, "DISCORD_BOT_TOKEN", "fake-token")

    asyncio.run(
        discord_listener.handle_message_delete(
            {"channel_id": "111111111111111111", "id": "999"},
            WATCHED,
        )
    )

    assert deleted == [("111111111111111111", "999")]
    assert cursor_updates == [("111111111111111111", "1000")]
    assert fetched_messages == [("fake-token", "111111111111111111", 1)]


def test_handle_message_delete_does_not_update_cursor_when_not_cursor(
    monkeypatch,
):
    """When the deleted message was NOT the cursor, cursor must not change."""
    deleted = []
    cursor_updates = []

    def fake_delete(channel_id, message_id):
        deleted.append((channel_id, message_id))
        return 1

    def fake_get_cursor(channel_id):
        return "888"  # Different from the message being deleted

    def fake_update_cursor(channel_id, msg_id):
        cursor_updates.append((channel_id, msg_id))

    monkeypatch.setattr(discord_listener, "delete_message_from_store", fake_delete)
    monkeypatch.setattr(discord_listener, "get_last_ingested_message_id", fake_get_cursor)
    monkeypatch.setattr(
        discord_listener, "update_last_ingested_message_id", fake_update_cursor
    )

    asyncio.run(
        discord_listener.handle_message_delete(
            {"channel_id": "111111111111111111", "id": "999"},
            WATCHED,
        )
    )

    assert deleted == [("111111111111111111", "999")]
    assert cursor_updates == []
