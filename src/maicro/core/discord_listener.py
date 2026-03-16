"""
Discord Gateway listener — real-time ingestion via discord.py.
Uses discord.Client to connect to the Discord Gateway.
"""

from __future__ import annotations

import asyncio
import logging

from maicro.core.ingestion import (
    _docs_from_discord_messages,
    delete_message_from_store,
    ingest_documents,
    update_message_in_store,
)
from maicro.core.state import update_last_ingested_message_id

logger = logging.getLogger(__name__)



async def handle_message_create(message: dict, channel_ids: set[str]) -> None:
    """
    Process a single MESSAGE_CREATE payload (as a plain dict).

    """
    channel_id = message.get("channel_id", "")
    if channel_id not in channel_ids:
        return

    docs = _docs_from_discord_messages([message], channel_id)
    if not docs:
        return

    
    count = await asyncio.to_thread(ingest_documents, docs)
    if count:
        update_last_ingested_message_id(channel_id, message["id"])
        logger.info("[listener] ingested %d doc(s) from channel %s", count, channel_id)

async def handle_message_delete(payload: dict, channel_ids: set[str]) -> None:
    """
    Process a MESSAGE_DELETE payload (plain dict).

    Expected keys: channel_id, id (message_id).
    Deletes the corresponding Qdrant point(s) if the channel is watched.
    Exposed at module level so unit tests can call it without a real Discord client.
    """
    channel_id = payload.get("channel_id", "")
    if channel_id not in channel_ids:
        return

    message_id = payload.get("id", "")
    if not message_id:
        return

    n = await asyncio.to_thread(delete_message_from_store, channel_id, message_id)
    logger.info(
        "[listener] deleted %d point(s) for message_id=%s channel=%s",
        n, message_id, channel_id,
    )


async def handle_message_update(payload: dict, channel_ids: set[str]) -> None:
    """
    Process a MESSAGE_UPDATE payload (plain dict).

    Expected keys: channel_id, id, content (plus optional author / embeds).
    Deletes the old Qdrant point(s) and re-ingests with the new content.
    Exposed at module level for unit-test access.
    """
    channel_id = payload.get("channel_id", "")
    if channel_id not in channel_ids:
        return

    count = await asyncio.to_thread(update_message_in_store, payload, channel_id)
    if count:
        logger.info(
            "[listener] updated message_id=%s in channel %s (%d doc(s))",
            payload.get("id"), channel_id, count,
        )
    else:
        logger.debug(
            "[listener] MESSAGE_UPDATE for message_id=%s had no indexable content — old point(s) removed",
            payload.get("id"),
        )



def _message_to_dict(msg) -> dict:
    
    return {
        "id": str(msg.id),
        "channel_id": str(msg.channel.id),
        "content": msg.content,
        "author": {"username": msg.author.name},
        "timestamp": msg.created_at.isoformat(),
        "embeds": [
            {
                "title": e.title or "",
                "description": e.description or "",
            }
            for e in msg.embeds
        ],
    }




async def run_discord_listener(bot_token: str, channel_ids: list[str]) -> None:
    """
    Connect to Discord via discord.py and listen for new messages forever.
    """
    if not bot_token:
        logger.error("[listener] DISCORD_BOT_TOKEN is not set — listener will not start")
        return
    if not channel_ids:
        logger.error("[listener] No channel IDs configured — listener will not start")
        return

    try:
        import discord
    except ImportError:
        logger.error(
            "[listener] discord.py is not installed. "
            "Add 'discord.py>=2.4.0' to your dependencies and reinstall."
        )
        return

    watched: set[str] = set(channel_ids)

    intents = discord.Intents(guilds=True, guild_messages=True, message_content=True)
    client = discord.Client(intents=intents)

    @client.event
    async def on_ready() -> None:
        logger.info(
            "[listener] READY — logged in as %s (id=%s)", client.user, client.user.id
        )

    @client.event
    async def on_message(msg: discord.Message) -> None:
        if msg.author.bot:
            return
        channel_id = str(msg.channel.id)
        logger.debug(
            "[listener] MESSAGE_CREATE channel=%s content=%r",
            channel_id,
            (msg.content or "")[:80],
        )
        await handle_message_create(_message_to_dict(msg), watched)

    @client.event
    async def on_raw_message_delete(payload: discord.RawMessageDeleteEvent) -> None:
        channel_id = str(payload.channel_id)
        message_id = str(payload.message_id)
        logger.debug(
            "[listener] MESSAGE_DELETE channel=%s message_id=%s", channel_id, message_id
        )
        await handle_message_delete(
            {"channel_id": channel_id, "id": message_id}, watched
        )

    @client.event
    async def on_raw_message_edit(payload: discord.RawMessageUpdateEvent) -> None:
        data: dict = payload.data
        channel_id = str(payload.channel_id)
        message_id = str(payload.message_id)
        logger.debug(
            "[listener] MESSAGE_UPDATE channel=%s message_id=%s", channel_id, message_id
        )
        msg_dict = {
            "id": message_id,
            "channel_id": channel_id,
            "content": data.get("content", ""),
            "author": data.get("author", {"username": "unknown"}),
            "timestamp": data.get("edited_timestamp") or data.get("timestamp", ""),
            "embeds": [
                {"title": e.get("title", ""), "description": e.get("description", "")}
                for e in data.get("embeds", [])
            ],
        }
        await handle_message_update(msg_dict, watched)

    MAX_RETRIES = 10
    BASE_DELAY = 5.0
    MAX_DELAY = 60.0

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            await client.start(bot_token)
            break  # clean exit (shouldn't normally happen)
        except discord.LoginFailure:
            logger.error(
                "[listener] Invalid Discord bot token (LoginFailure) — will not retry"
            )
            return
        except Exception as exc:
            delay = min(BASE_DELAY * 2 ** (attempt - 1), MAX_DELAY)
            logger.warning(
                "[listener] Disconnected (attempt %d/%d): %s. Retrying in %.0fs…",
                attempt, MAX_RETRIES, exc, delay,
            )
            # Close the old client before reconnecting
            try:
                await client.close()
            except Exception:
                pass
            await asyncio.sleep(delay)
            # Re-create the client for a clean reconnect and re-register all events
            client = discord.Client(intents=intents)

            @client.event
            async def on_ready() -> None:
                logger.info(
                    "[listener] READY — logged in as %s (id=%s)", client.user, client.user.id
                )

            @client.event
            async def on_message(msg: discord.Message) -> None:
                if msg.author.bot:
                    return
                channel_id = str(msg.channel.id)
                logger.debug(
                    "[listener] MESSAGE_CREATE channel=%s content=%r",
                    channel_id,
                    (msg.content or "")[:80],
                )
                await handle_message_create(_message_to_dict(msg), watched)

            @client.event
            async def on_raw_message_delete(payload: discord.RawMessageDeleteEvent) -> None:
                channel_id = str(payload.channel_id)
                message_id = str(payload.message_id)
                logger.debug(
                    "[listener] MESSAGE_DELETE channel=%s message_id=%s", channel_id, message_id
                )
                await handle_message_delete(
                    {"channel_id": channel_id, "id": message_id}, watched
                )

            @client.event
            async def on_raw_message_edit(payload: discord.RawMessageUpdateEvent) -> None:
                data: dict = payload.data
                channel_id = str(payload.channel_id)
                message_id = str(payload.message_id)
                logger.debug(
                    "[listener] MESSAGE_UPDATE channel=%s message_id=%s", channel_id, message_id
                )
                # Build a normalised dict compatible with handle_message_update.
                msg_dict = {
                    "id": message_id,
                    "channel_id": channel_id,
                    "content": data.get("content", ""),
                    "author": data.get("author", {"username": "unknown"}),
                    "timestamp": data.get("edited_timestamp") or data.get("timestamp", ""),
                    "embeds": [
                        {"title": e.get("title", ""), "description": e.get("description", "")}
                        for e in data.get("embeds", [])
                    ],
                }
                await handle_message_update(msg_dict, watched)
    else:
        logger.error(
            "[listener] Exhausted %d reconnect attempts — giving up.", MAX_RETRIES
        )
