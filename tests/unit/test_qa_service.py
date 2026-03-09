from types import SimpleNamespace

from maicro.services import qa_service


def test_ask_question_uses_latest_shortcut(monkeypatch):
    monkeypatch.setattr(qa_service, "_latest_discord_message", lambda: "latest-message")
    monkeypatch.setattr(
        qa_service,
        "_invoke_with_timeout",
        lambda chain, question, timeout_seconds=30: chain.invoke(question),
    )

    class FakeLLM:
        def invoke(self, _prompt):
            return SimpleNamespace(content="LLM formatted latest answer")

    monkeypatch.setattr(qa_service, "get_llm", lambda: FakeLLM())

    answer = qa_service.ask_question("whats the last message")

    assert answer == "LLM formatted latest answer"


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


def test_normalize_question_rewrites_common_broken_phrase():
    normalized = qa_service._normalize_question("whats the we have today")
    assert normalized.lower() == "what is do we have today"


def test_retrieve_with_rewrites_merges_when_rewrite_changes_query(monkeypatch):
    original_doc = SimpleNamespace(
        page_content="original result",
        metadata={"source": "discord", "message_id": "1"},
    )
    normalized_doc = SimpleNamespace(
        page_content="normalized result",
        metadata={"source": "discord", "message_id": "2"},
    )

    class FakeRetriever:
        def invoke(self, query):
            if query == "whats the we have today":
                return [original_doc]
            return [normalized_doc]

    docs = qa_service._retrieve_with_rewrites("whats the we have today", FakeRetriever(), k=6)

    assert len(docs) == 2
    assert docs[0].page_content == "original result"
    assert docs[1].page_content == "normalized result"


def test_augment_temporal_question_adds_reference_date():
    augmented = qa_service._augment_temporal_question("what do we have today")
    assert "Reference date (UTC): " in augmented


def test_augment_temporal_question_keeps_non_temporal_query():
    question = "who is the dev manager"
    assert qa_service._augment_temporal_question(question) == question
