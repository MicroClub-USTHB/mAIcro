"""
Unit tests for discord_listener.handle_message_create.

We test the dict-based handler in isolation — no real Discord connection or
Qdrant needed.  The discord.py import only happens inside run_discord_listener(),
so these tests work without discord.py installed.
"""

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from maicro.core import discord_listener


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
    monkeypatch.setattr(discord_listener, "ingest_documents", lambda docs: called.append(docs) or 0)

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
    with caplog.at_level(logging.ERROR, logger="maicro.core.discord_listener"):
        asyncio.run(discord_listener.run_discord_listener("", ["111"]))
    assert any("DISCORD_BOT_TOKEN" in r.message for r in caplog.records)


def test_run_discord_listener_returns_early_without_channels(caplog):
    """Missing channel list must log an error and return without connecting."""
    import logging
    with caplog.at_level(logging.ERROR, logger="maicro.core.discord_listener"):
        asyncio.run(discord_listener.run_discord_listener("some-token", []))
    assert any("No channel IDs" in r.message for r in caplog.records)
