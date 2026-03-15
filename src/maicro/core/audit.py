"""
Audit module — handles startup reconciliation of offline edits and deletes.

This module provides the `run_startup_audit()` function which:
  1. Fetches recent messages from Discord per channel
  2. Compares with Qdrant vector store contents
  3. Removes stale points (deleted while offline)
  4. Updates changed points (edited while offline)

This separates audit concerns from the core ingestion pipeline.
"""


from maicro.core.config import settings
from maicro.core.discord_fetcher import fetch_channel_messages
import logging

logger = logging.getLogger(__name__)


DISCORD_API = "https://discord.com/api/v10"


async def _check_message_exists_in_discord(
    bot_token: str,
    channel_id: str,
    message_id: str,
) -> bool:
    """
    Check if a specific message still exists in Discord.
    Returns True if the message exists, False if it was deleted (404).
    Returns None on error or rate limit (to skip verification).
    """
    import aiohttp

    headers = {"Authorization": f"Bot {bot_token}"}
    url = f"{DISCORD_API}/channels/{channel_id}/messages/{message_id}"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as resp:
                if resp.status == 200:
                    return True
                elif resp.status == 404:
                    return False
                elif resp.status == 429:
                    logger.warning(
                        "[audit] Rate limited when checking message %s in channel %s - skipping verification",
                        message_id, channel_id,
                    )
                    return None
                else:
                    logger.warning(
                        "[audit] Unexpected status %s checking message %s in channel %s",
                        resp.status, message_id, channel_id,
                    )
                    return True
    except Exception as e:
        logger.warning(
            "[audit] Error checking message %s in channel %s: %s",
            message_id, channel_id, e,
        )
        return True  


async def run_startup_audit(
    channel_ids: list[str],
    window: int = 1000,
) -> dict:
    """
    For each channel:
      1. Fetch the last `window` messages from Discord REST.
      2. Scroll Qdrant for points whose message_id appears in that window.
      3. For each Qdrant point:
           - Message no longer on Discord → deleted while offline → remove point.
           - Message content changed     → edited while offline  → delete + re-ingest.
      4. No action for unchanged messages.

    """
    from qdrant_client.http import models as qdrant_models

    # Lazy imports to avoid circular dependency
    from maicro.core.ingestion import (
        _bootstrap_collection,
        _docs_from_discord_messages,
        delete_message_from_store,
        update_message_in_store,
        get_qdrant_client,
    )

    if not settings.DISCORD_BOT_TOKEN or not channel_ids:
        return {}

    summary: dict[str, dict] = {}

    for channel_id in channel_ids:
        deleted = 0
        updated = 0
        errors_list: list[str] = []

        try:
            # Step 1 — fetch recent Discord messages (newest-first, no after cursor)
            recent: list[dict] = await fetch_channel_messages(
                bot_token=settings.DISCORD_BOT_TOKEN,
                channel_id=channel_id,
                limit=window,
            )
            
            discord_index: dict[str, str] = {}
            for msg in recent:
                docs = _docs_from_discord_messages([msg], channel_id)
                msg_id_str = str(msg["id"])
                discord_index[msg_id_str] = docs[0].page_content if docs else ""
            if not discord_index:
                summary[channel_id] = {"deleted": 0, "updated": 0}
                continue

            
            try:
                _bootstrap_collection()
            except Exception as e:
                logger.warning(f"[audit] Failed to bootstrap collection: {e}")

            client = get_qdrant_client()

            total_count_result = client.count(
                collection_name=settings.COLLECTION_NAME,
                count_filter=qdrant_models.Filter(
                    must=[
                        qdrant_models.FieldCondition(
                            key="metadata.channel_id",
                            match=qdrant_models.MatchValue(value=channel_id),
                        ),
                    ]
                ),
                exact=True,
            )
            logger.info(
                "[audit] Channel %s has %d total points in Qdrant, discord_index has %d message IDs",
                channel_id, total_count_result.count, len(discord_index),
            )

            discord_index_sample = list(discord_index.keys())[:5]
            

            # Scroll ALL points in this channel (no filter on message_id)
            all_points_filter = qdrant_models.Filter(
                must=[
                    qdrant_models.FieldCondition(
                        key="metadata.channel_id",
                        match=qdrant_models.MatchValue(value=channel_id),
                    ),
                ],
            )

            offset = None
            while True:
                scroll_result = client.scroll(
                    collection_name=settings.COLLECTION_NAME,
                    scroll_filter=all_points_filter,
                    limit=100,
                    offset=offset,
                    with_payload=True,
                    with_vectors=False,
                )
                points, next_offset = scroll_result

                for point in points:
                    payload = point.payload or {}
                    meta = payload.get("metadata", {})
                    msg_id: str = meta.get("message_id", "")
                    stored_content: str = (payload.get("page_content") or "").strip()

                    # Skip points without message_id
                    if not msg_id:
                        continue

                    # Ensure we're using string for comparison
                    msg_id_str = str(msg_id)

                    # Debug: Log what we're comparing
                    logger.debug(
                        "[audit] Checking msg_id=%s (type=%s) - in discord_index=%s",
                        msg_id_str, type(msg_id), msg_id_str in discord_index,
                    )

                    # Case 1: message_id NOT in discord_index → message was deleted while offline
                    if msg_id_str not in discord_index:
                        n = delete_message_from_store(channel_id, msg_id_str)
                        deleted += n
                        if n:
                            logger.info(
                                "[audit] deleted message_id=%s from channel %s (was deleted offline)",
                                msg_id_str, channel_id,
                            )
                        else:
                            # Message not in discord_index but also not found in Qdrant to delete
                            # This could happen if the message was already deleted previously
                            logger.debug(
                                "[audit] message_id=%s not in discord_index but no Qdrant points to delete",
                                msg_id_str,
                            )
                        continue

                    # Log that we verified this message exists in both Discord and Qdrant
                    logger.debug(
                        "[audit] Verified message_id=%s exists in both Discord and Qdrant",
                        msg_id_str,
                    )

                    # Case 1b: Even if message_id IS in discord_index, verify it still exists
                    # This handles edge cases where Discord's batch API might return deleted messages
                    # or messages that were soft-deleted
                    exists = await _check_message_exists_in_discord(
                        bot_token=settings.DISCORD_BOT_TOKEN,
                        channel_id=channel_id,
                        message_id=msg_id_str,
                    )
                    if not exists:
                        n = delete_message_from_store(channel_id, msg_id_str)
                        deleted += n
                        if n:
                            logger.info(
                                "[audit] deleted message_id=%s from channel %s (verified deleted via API)",
                                msg_id_str, channel_id,
                            )
                        continue

                    # Case 2: message_id IS in discord_index but content changed → edited while offline
                    current_content = discord_index.get(msg_id_str, "")
                    if stored_content != current_content:
                        msg_dict = next(
                            (m for m in recent if str(m["id"]) == msg_id_str), None
                        )
                        if msg_dict:
                            update_message_in_store(msg_dict, channel_id)
                            updated += 1
                            logger.info(
                                "[audit] updated message_id=%s in channel %s (edited offline)",
                                msg_id_str, channel_id,
                            )

                if next_offset is None:
                    break
                offset = next_offset

            logger.info(
                "[audit] Channel %s audit complete: deleted=%d, updated=%d",
                channel_id, deleted, updated,
            )

        except Exception as exc:
            logger.warning("[audit] Unexpected error for channel %s: %s", channel_id, exc)
            errors_list.append(str(exc))

        summary[channel_id] = {"deleted": deleted, "updated": updated, "errors": errors_list}
        logger.info(
            "[audit] channel=%s  deleted=%d  updated=%d",
            channel_id, deleted, updated,
        )

    return summary