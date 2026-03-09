from types import SimpleNamespace

from maicro.services import qa_service


def test_ask_question_uses_latest_shortcut(monkeypatch):
    monkeypatch.setattr(qa_service, "_latest_discord_message", lambda: "latest-message")

    def _should_not_run():
        raise AssertionError("get_llm should not be called for latest-message intent")

    monkeypatch.setattr(qa_service, "get_llm", _should_not_run)

    answer = qa_service.ask_question("whats the last message")

    assert answer == "latest-message"


def test_latest_discord_message_picks_newest_timestamp(monkeypatch):
    points = [
        SimpleNamespace(
            payload={
                "page_content": "[a] older message",
                "metadata": {
                    "source": "discord",
                    "author": "a",
                    "channel_id": "c1",
                    "timestamp": "2026-03-01T10:00:00+00:00",
                },
            }
        ),
        SimpleNamespace(
            payload={
                "page_content": "[b] newest message",
                "metadata": {
                    "source": "discord",
                    "author": "b",
                    "channel_id": "c2",
                    "timestamp": "2026-03-09T17:39:33+00:00",
                },
            }
        ),
    ]

    class FakeClient:
        def scroll(self, **_kwargs):
            return points, None

    fake_vector_store = SimpleNamespace(
        client=FakeClient(),
        collection_name="microclub_knowledge",
    )
    monkeypatch.setattr(qa_service, "get_vector_store", lambda: fake_vector_store)

    result = qa_service._latest_discord_message()

    assert result is not None
    assert "author: b" in result
    assert "channel_id: c2" in result
    assert "newest message" in result
