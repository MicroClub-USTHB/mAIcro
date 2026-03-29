"""
Audit module — handles startup reconciliation of offline edits and deletes.
"""

import logging

from core.config import settings
from core.discord_fetcher import fetch_channel_messages, fetch_message_by_id
from core.state import (
    get_last_ingested_message_id,
    ensure_channel_in_state,
    update_last_ingested_message_id,
)

logger = logging.getLogger(__name__)


def _message_id_to_int(message_id: str) -> int | None:
    try:
        return int(str(message_id))
    except (TypeError, ValueError):
        return None


async def run_startup_audit(
    channel_ids: list[str],
    window: int = 1000,
) -> dict:

    from qdrant_client.http import models as qdrant_models

    from core.ingestion import (
        _bootstrap_collection,
        _docs_from_discord_messages,
        delete_message_from_store,
        update_message_in_store,
        get_qdrant_client,
    )

    if not settings.DISCORD_BOT_TOKEN or not channel_ids:
        return {}

    try:
        _bootstrap_collection()
        client = get_qdrant_client()
        prune_filter = qdrant_models.Filter(
            must=[
                qdrant_models.FieldCondition(
                    key="metadata.source",
                    match=qdrant_models.MatchAny(any=["discord", "ingestion_cursor"]),
                )
            ],
            must_not=[
                qdrant_models.FieldCondition(
                    key="metadata.channel_id",
                    match=qdrant_models.MatchAny(any=channel_ids),
                )
            ],
        )
        prune_count = client.count(
            collection_name=settings.COLLECTION_NAME,
            count_filter=prune_filter,
            exact=True,
        )
        if prune_count.count > 0:
            client.delete(
                collection_name=settings.COLLECTION_NAME,
                points_selector=qdrant_models.FilterSelector(filter=prune_filter),
            )
            logger.info(
                "[audit] Pruned %d stale points from removed channels.", prune_count.count
            )
    except Exception as e:
        logger.warning(f"[audit] Failed to prune removed channels: {e}")

    summary: dict[str, dict] = {}


    for channel_id in channel_ids:
        ensure_channel_in_state(channel_id)

        deleted = 0
        updated = 0
        errors_list: list[str] = []

        try:
            last_message_id = get_last_ingested_message_id(channel_id)

            if not last_message_id:
                logger.info(
                    "[audit] Channel %s: no cursor found or channel never ingested, skipping audit",
                    channel_id,
                )
                summary[channel_id] = {
                    "deleted": 0,
                    "updated": 0,
                    "skipped": "new_channel",
                }
                continue

            cursor_msg = await fetch_message_by_id(
                bot_token=settings.DISCORD_BOT_TOKEN,
                channel_id=channel_id,
                message_id=last_message_id,
            )

            if cursor_msg is None:
                logger.info(
                    "[audit] Channel %s: cursor message %s was deleted, searching for new cursor",
                    channel_id,
                    last_message_id,
                )
                recent_messages: list[dict] = await fetch_channel_messages(
                    bot_token=settings.DISCORD_BOT_TOKEN,
                    channel_id=channel_id,
                    limit=1,
                )
                if recent_messages:
                    new_cursor = recent_messages[0]["id"]
                    logger.info(
                        "[audit] Channel %s: updating cursor from %s to %s",
                        channel_id,
                        last_message_id,
                        new_cursor,
                    )
                    update_last_ingested_message_id(channel_id, new_cursor)
                    last_message_id = new_cursor
                    cursor_msg = recent_messages[0]
                else:
                    logger.warning(
                        "[audit] Channel %s: no messages found in channel at all",
                        channel_id,
                    )
                    summary[channel_id] = {
                        "deleted": 0,
                        "updated": 0,
                        "skipped": "channel_empty",
                    }
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
                    cursor_stored_content = (
                        cursor_points[0].payload.get("page_content") or ""
                    ).strip()
            except Exception as e:
                logger.warning(f"[audit] Failed to get cursor content from Qdrant: {e}")

            cursor_docs = _docs_from_discord_messages([cursor_msg], channel_id)
            cursor_content = cursor_docs[0].page_content if cursor_docs else ""

            if cursor_stored_content and cursor_content != cursor_stored_content:
                logger.info(
                    "[audit] Cursor message %s was edited, updating in Qdrant",
                    cursor_id_str,
                )
                update_message_in_store(cursor_msg, channel_id)
                updated += 1

            recent: list[dict] = await fetch_channel_messages(
                bot_token=settings.DISCORD_BOT_TOKEN,
                channel_id=channel_id,
                limit=window,
                before=last_message_id,
            )

            discord_index: dict[str, str] = {}
            recent_lookup: dict[str, dict] = {}
            cursor_id_str = str(cursor_msg["id"])
            discord_index[cursor_id_str] = cursor_content

            for msg in recent:
                docs = _docs_from_discord_messages([msg], channel_id)
                msg_id_str = str(msg["id"])
                discord_index[msg_id_str] = docs[0].page_content if docs else ""
                recent_lookup[msg_id_str] = msg
            if not discord_index:
                logger.info(
                    "[audit] Channel %s: no messages before cursor to audit",
                    channel_id,
                )
                summary[channel_id] = {
                    "deleted": 0,
                    "updated": 0,
                    "skipped": "no_messages_before_cursor",
                }
                continue

            cursor_id_int = _message_id_to_int(cursor_id_str)
            audited_ids = [
                parsed_id
                for parsed_id in (
                    _message_id_to_int(msg_id) for msg_id in discord_index
                )
                if parsed_id is not None
            ]
            audit_lower_bound = min(audited_ids) if audited_ids else cursor_id_int
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
                channel_id,
                total_count_result.count,
                len(discord_index),
            )
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
                    msg_id_int = _message_id_to_int(msg_id_str)
                    if msg_id_int is None:
                        logger.debug(
                            "[audit] Skipping non-numeric message_id=%s", msg_id_str
                        )
                        continue
                    if (
                        audit_lower_bound is not None
                        and cursor_id_int is not None
                        and not audit_lower_bound <= msg_id_int <= cursor_id_int
                    ):
                        logger.debug(
                            "[audit] Skipping message_id=%s outside audited window [%s, %s]",
                            msg_id_str,
                            audit_lower_bound,
                            cursor_id_int,
                        )
                        continue
                    logger.debug(
                        "[audit] Checking msg_id=%s (type=%s) - in discord_index=%s",
                        msg_id_str,
                        type(msg_id),
                        msg_id_str in discord_index,
                    )
                    if msg_id_str not in discord_index:
                        n = delete_message_from_store(channel_id, msg_id_str)
                        deleted += n
                        if n:
                            logger.info(
                                "[audit] deleted message_id=%s from channel %s (was deleted offline)",
                                msg_id_str,
                                channel_id,
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
                            msg_dict = recent_lookup.get(msg_id_str)
                        if msg_dict:
                            update_message_in_store(msg_dict, channel_id)
                            updated += 1
                            logger.info(
                                "[audit] updated message_id=%s in channel %s (edited offline)",
                                msg_id_str,
                                channel_id,
                            )

                if next_offset is None:
                    break
                offset = next_offset

            logger.info(
                "[audit] Channel %s audit complete: deleted=%d, updated=%d",
                channel_id,
                deleted,
                updated,
            )

        except Exception as exc:
            logger.warning(
                "[audit] Unexpected error for channel %s: %s", channel_id, exc
            )
            errors_list.append(str(exc))

        summary[channel_id] = {
            "deleted": deleted,
            "updated": updated,
            "errors": errors_list,
        }
        logger.info(
            "[audit] channel=%s  deleted=%d  updated=%d",
            channel_id,
            deleted,
            updated,
        )

    return summary
