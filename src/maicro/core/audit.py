"""
Audit module — handles startup reconciliation of offline edits and deletes.
"""


from maicro.core.config import settings
from maicro.core.discord_fetcher import fetch_channel_messages, fetch_message_by_id
from maicro.core.state import get_last_ingested_message_id, ensure_channel_in_state, update_last_ingested_message_id
import logging

logger = logging.getLogger(__name__)


DISCORD_API = "https://discord.com/api/v10"


async def run_startup_audit(
    channel_ids: list[str],
    window: int = 1000,
) -> dict:
 


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
        # Ensure channel exists in state before auditing
        ensure_channel_in_state(channel_id)
        
        deleted = 0
        updated = 0
        errors_list: list[str] = []

        try:
            # Step 1 — get cursor from state (last ingested message ID)
            last_message_id = get_last_ingested_message_id(channel_id)

            # Skip audit for new channels (no cursor or empty cursor = nothing to check)
            if not last_message_id:
                logger.info(
                    "[audit] Channel %s: no cursor found or channel never ingested, skipping audit",
                    channel_id,
                )
                summary[channel_id] = {"deleted": 0, "updated": 0, "skipped": "new_channel"}
                continue

            # First, check if the cursor message still exists in Discord (it might have been deleted)
            cursor_msg = await fetch_message_by_id(
                bot_token=settings.DISCORD_BOT_TOKEN,
                channel_id=channel_id,
                message_id=last_message_id,
            )
            
            # If cursor message was deleted, we need to find a new cursor
            if cursor_msg is None:
                logger.info(
                    "[audit] Channel %s: cursor message %s was deleted, searching for new cursor",
                    channel_id, last_message_id,
                )
                # Fetch the most recent message to use as new cursor
                recent_messages: list[dict] = await fetch_channel_messages(
                    bot_token=settings.DISCORD_BOT_TOKEN,
                    channel_id=channel_id,
                    limit=1,
                )
                if recent_messages:
                    new_cursor = recent_messages[0]["id"]
                    logger.info(
                        "[audit] Channel %s: updating cursor from %s to %s",
                        channel_id, last_message_id, new_cursor,
                    )
                    update_last_ingested_message_id(channel_id, new_cursor)
                    last_message_id = new_cursor
                    cursor_msg = recent_messages[0]
                else:
                    # No messages in channel at all
                    logger.warning(
                        "[audit] Channel %s: no messages found in channel at all",
                        channel_id,
                    )
                    summary[channel_id] = {"deleted": 0, "updated": 0, "skipped": "channel_empty"}
                    continue
            
            # Check if cursor message was edited - get stored content from Qdrant
            cursor_id_str = str(cursor_msg["id"])
            
            # Get the stored content for cursor from Qdrant
            cursor_stored_content = ""
            try:
                client = get_qdrant_client()
                search_result = client.scroll(
                    collection_name=settings.COLLECTION_NAME,
                    scroll_filter=qdrant_models.Filter(
                        must=[
                            qdrant_models.FieldCondition(
                                key="metadata.message_id",
                                match=qdrant_models.MatchValue(value=cursor_id_str),
                            ),
                        ]
                    ),
                    limit=1,
                    with_payload=True,
                    with_vectors=False,
                )
                cursor_points, _ = search_result
                if cursor_points:
                    cursor_stored_content = (cursor_points[0].payload.get("page_content") or "").strip()
            except Exception as e:
                logger.warning(f"[audit] Failed to get cursor content from Qdrant: {e}")
            
            cursor_docs = _docs_from_discord_messages([cursor_msg], channel_id)
            cursor_content = cursor_docs[0].page_content if cursor_docs else ""
            
            # If cursor was edited, update it immediately
            if cursor_stored_content and cursor_content != cursor_stored_content:
                logger.info(
                    "[audit] Cursor message %s was edited, updating in Qdrant",
                    cursor_id_str,
                )
                update_message_in_store(cursor_msg, channel_id)
                updated += 1
            
            # Now fetch messages before the cursor for audit
            recent: list[dict] = await fetch_channel_messages(
                bot_token=settings.DISCORD_BOT_TOKEN,
                channel_id=channel_id,
                limit=window,  # limit to avoid excessive API calls
                before=last_message_id,
            )
            
            discord_index: dict[str, str] = {}
            # Add cursor message to discord_index for editing check
            cursor_id_str = str(cursor_msg["id"])
            discord_index[cursor_id_str] = cursor_content
            
            for msg in recent:
                docs = _docs_from_discord_messages([msg], channel_id)
                msg_id_str = str(msg["id"])
                discord_index[msg_id_str] = docs[0].page_content if docs else ""
            if not discord_index:
                logger.info(
                    "[audit] Channel %s: no messages before cursor to audit",
                    channel_id,
                )
                summary[channel_id] = {"deleted": 0, "updated": 0, "skipped": "no_messages_before_cursor"}
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
                "[audit] Channel %s: checking %d Qdrant points against %d messages before cursor",
                channel_id, total_count_result.count, len(discord_index),
            )
            discord_index_sample = list(discord_index.keys())[:5]
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
                    if not msg_id:
                        continue
                    msg_id_str = str(msg_id)
                    logger.debug(
                        "[audit] Checking msg_id=%s (type=%s) - in discord_index=%s",
                        msg_id_str, type(msg_id), msg_id_str in discord_index,
                    )
                    if msg_id_str not in discord_index:
                        n = delete_message_from_store(channel_id, msg_id_str)
                        deleted += n
                        if n:
                            logger.info(
                                "[audit] deleted message_id=%s from channel %s (was deleted offline)",
                                msg_id_str, channel_id,
                            )
                        else:
                           
                            logger.debug(
                                "[audit] message_id=%s not in discord_index but no Qdrant points to delete",
                                msg_id_str,
                            )
                        continue
                    logger.debug(
                        "[audit] Verified message_id=%s exists in both Discord and Qdrant",
                        msg_id_str,
                    )
                    current_content = discord_index.get(msg_id_str, "")
                    if stored_content != current_content:
                        if msg_id_str == cursor_id_str:
                            msg_dict = cursor_msg
                        else:
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