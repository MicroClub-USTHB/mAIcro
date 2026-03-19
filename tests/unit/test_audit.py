import asyncio
from types import SimpleNamespace

from core import audit
from core import ingestion


def _message(message_id: str, content: str) -> dict:
    return {
        "id": message_id,
        "content": content,
        "author": {"username": "alice"},
        "timestamp": f"2026-03-10T08:0{message_id[-1]}:00+00:00",
        "embeds": [],
    }


def _point(message_id: str, channel_id: str, content: str):
    return SimpleNamespace(
        payload={
            "page_content": f"[alice] {content}",
            "metadata": {
                "channel_id": channel_id,
                "message_id": message_id,
                "source": "discord",
            },
        }
    )


def test_startup_audit_does_not_delete_messages_older_than_audited_window(monkeypatch):
    channel_id = "chan-1"
    deleted_ids: list[str] = []

    cursor_msg = _message("1005", "cursor")
    recent_messages = [
        _message("1004", "recent-1"),
        _message("1003", "recent-2"),
    ]
    qdrant_points = [
        _point("1002", channel_id, "older-outside-window"),
        _point("1003", channel_id, "recent-2"),
        _point("1004", channel_id, "recent-1"),
        _point("1005", channel_id, "cursor"),
    ]

    class FakeClient:
        def scroll(self, **kwargs):
            filter_obj = kwargs.get("scroll_filter")
            conditions = getattr(filter_obj, "must", []) if filter_obj else []
            message_ids = [
                getattr(getattr(cond, "match", None), "value", None)
                for cond in conditions
                if getattr(cond, "key", None) == "metadata.message_id"
            ]
            if message_ids == ["1005"]:
                return [_point("1005", channel_id, "cursor")], None
            return qdrant_points, None

        def count(self, **_kwargs):
            return SimpleNamespace(count=len(qdrant_points))

    async def fake_fetch_message_by_id(**_kwargs):
        return cursor_msg

    async def fake_fetch_channel_messages(**_kwargs):
        return recent_messages

    monkeypatch.setattr(audit, "get_last_ingested_message_id", lambda _channel_id: "1005")
    monkeypatch.setattr(audit, "fetch_message_by_id", fake_fetch_message_by_id)
    monkeypatch.setattr(audit, "fetch_channel_messages", fake_fetch_channel_messages)
    monkeypatch.setattr(audit, "ensure_channel_in_state", lambda _channel_id: None)
    monkeypatch.setattr(ingestion, "_bootstrap_collection", lambda: None)
    monkeypatch.setattr(ingestion, "get_qdrant_client", lambda: FakeClient())
    monkeypatch.setattr(
        ingestion,
        "delete_message_from_store",
        lambda _channel_id, message_id: deleted_ids.append(message_id) or 1,
    )
    monkeypatch.setattr(ingestion, "update_message_in_store", lambda *_args, **_kwargs: 0)

    summary = asyncio.run(audit.run_startup_audit([channel_id], window=2))

    assert deleted_ids == []
    assert summary[channel_id]["deleted"] == 0
    assert summary[channel_id]["updated"] == 0


def test_startup_audit_deletes_missing_message_within_audited_window(monkeypatch):
    channel_id = "chan-1"
    deleted_ids: list[str] = []

    cursor_msg = _message("1005", "cursor")
    recent_messages = [
        _message("1003", "recent-2"),
        _message("1002", "recent-3"),
    ]
    qdrant_points = [
        _point("1002", channel_id, "recent-3"),
        _point("1003", channel_id, "recent-2"),
        _point("1004", channel_id, "deleted-offline"),
        _point("1005", channel_id, "cursor"),
    ]

    class FakeClient:
        def scroll(self, **kwargs):
            filter_obj = kwargs.get("scroll_filter")
            conditions = getattr(filter_obj, "must", []) if filter_obj else []
            message_ids = [
                getattr(getattr(cond, "match", None), "value", None)
                for cond in conditions
                if getattr(cond, "key", None) == "metadata.message_id"
            ]
            if message_ids == ["1005"]:
                return [_point("1005", channel_id, "cursor")], None
            return qdrant_points, None

        def count(self, **_kwargs):
            return SimpleNamespace(count=len(qdrant_points))

    async def fake_fetch_message_by_id(**_kwargs):
        return cursor_msg

    async def fake_fetch_channel_messages(**_kwargs):
        return recent_messages

    monkeypatch.setattr(audit, "get_last_ingested_message_id", lambda _channel_id: "1005")
    monkeypatch.setattr(audit, "fetch_message_by_id", fake_fetch_message_by_id)
    monkeypatch.setattr(audit, "fetch_channel_messages", fake_fetch_channel_messages)
    monkeypatch.setattr(audit, "ensure_channel_in_state", lambda _channel_id: None)
    monkeypatch.setattr(ingestion, "_bootstrap_collection", lambda: None)
    monkeypatch.setattr(ingestion, "get_qdrant_client", lambda: FakeClient())
    monkeypatch.setattr(
        ingestion,
        "delete_message_from_store",
        lambda _channel_id, message_id: deleted_ids.append(message_id) or 1,
    )
    monkeypatch.setattr(ingestion, "update_message_in_store", lambda *_args, **_kwargs: 0)

    summary = asyncio.run(audit.run_startup_audit([channel_id], window=2))

    assert deleted_ids == ["1004"]
    assert summary[channel_id]["deleted"] == 1
    assert summary[channel_id]["updated"] == 0
