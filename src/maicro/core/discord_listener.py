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

    intents = discord.Intents(guild_messages=True, message_content=True)
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

    try:
        await client.start(bot_token)
    except discord.LoginFailure:
        logger.error(
            "[listener] Invalid Discord bot token (LoginFailure) — listener will not restart"
        )
    except Exception as exc:
        logger.error("[listener] Unexpected error in Discord listener: %s", exc)
        raise
