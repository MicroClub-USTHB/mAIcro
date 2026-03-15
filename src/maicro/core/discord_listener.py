"""
Discord Gateway listener — real-time ingestion via discord.py.
Uses discord.Client to connect to the Discord Gateway.
"""

from __future__ import annotations

import asyncio
import logging

from maicro.core.ingestion import _docs_from_discord_messages, ingest_documents
from maicro.core.state import update_last_ingested_message_id

logger = logging.getLogger(__name__)



async def handle_message_create(message: dict, channel_ids: set[str]) -> None:
    """
    Process a single MESSAGE_CREATE payload (as a plain dict).

    Ingests the message if it belongs to a watched channel.
    Exposed at module level so unit tests can call it directly without
    needing a real discord.Client.
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

    
    MAX_RETRIES = 10
    BASE_DELAY = 5.0   # seconds
    MAX_DELAY = 60.0   # seconds

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
            # Re-create the client for a clean reconnect
            client = discord.Client(intents=intents)
            client.event(on_ready)
            client.event(on_message)
    else:
        logger.error(
            "[listener] Exhausted %d reconnect attempts — giving up.", MAX_RETRIES
        )
