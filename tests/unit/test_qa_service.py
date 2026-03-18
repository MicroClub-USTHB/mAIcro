from types import SimpleNamespace

import pytest
from langchain_core.runnables import RunnableLambda

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
                "page_content": "[b] newest message",
                "metadata": {
                    "source": "discord",
                    "author": "b",
                    "channel_id": "c2",
                    "timestamp": "2026-03-09T17:39:33+00:00",
                },
            }
        ),
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


def test_today_updates_query_uses_llm_summary(monkeypatch):
    monkeypatch.setattr(qa_service, "_is_today_updates_query", lambda _q: True)
    monkeypatch.setattr(qa_service, "_today_discord_messages", lambda reference_date: [{"metadata": {"timestamp": "2026-03-09T12:00:00+00:00", "author": "u"}, "page_content": "Meeting at 2pm"}])
    monkeypatch.setattr(qa_service, "_invoke_with_timeout", lambda chain, question, timeout_seconds=30: chain.invoke(question))

    class FakeLLM:
        def invoke(self, _prompt):
            return SimpleNamespace(content="Today summary")

    monkeypatch.setattr(qa_service, "get_llm", lambda: FakeLLM())

    answer = qa_service.ask_question("whats the we have today")
    assert answer == "Today summary"


def test_today_updates_pattern_matches_whats_phrase():
    assert qa_service._is_today_updates_query("whats the we have today")


def test_retrieve_with_rewrites_deduplicates_results():
    shared_doc = SimpleNamespace(
        page_content="same result",
        metadata={"source": "discord", "message_id": "same"},
    )

    class FakeRetriever:
        def invoke(self, _query):
            return [shared_doc]

    docs = qa_service._retrieve_with_rewrites("whats the we have today", FakeRetriever(), k=6)

    assert len(docs) == 1
    assert docs[0].page_content == "same result"


def test_today_updates_without_today_messages_falls_back_to_latest(monkeypatch):
    monkeypatch.setattr(qa_service, "_is_today_updates_query", lambda _q: True)
    monkeypatch.setattr(qa_service, "_today_discord_messages", lambda reference_date: [])
    monkeypatch.setattr(qa_service, "_latest_discord_message", lambda: "Latest Discord message:\n- content: fallback")
    monkeypatch.setattr(
        qa_service,
        "_invoke_with_timeout",
        lambda chain, question, timeout_seconds=30: chain.invoke(question),
    )

    class FakeLLM:
        def invoke(self, _prompt):
            return SimpleNamespace(content="Fallback latest summary")

    monkeypatch.setattr(qa_service, "get_llm", lambda: FakeLLM())

    answer = qa_service.ask_question("what do we have today")
    assert answer == "Fallback latest summary"



def test_ask_question_recency_query_returns_latest_message_when_llm_fails(monkeypatch):
    latest_message = "Latest Discord message:\n- content: fallback"

    monkeypatch.setattr(qa_service, "_latest_discord_message", lambda: latest_message)
    monkeypatch.setattr(
        qa_service,
        "get_llm",
        lambda: (_ for _ in ()).throw(RuntimeError("gemini unavailable")),
    )

    answer = qa_service.ask_question("what is the last message")

    assert answer == latest_message


def test_ask_question_errors_when_qdrant_is_locked(monkeypatch):
    monkeypatch.setattr(qa_service, "get_llm", lambda: RunnableLambda(lambda _prompt: "ignored"))
    monkeypatch.setattr(
        qa_service,
        "get_hybrid_retriever",
        lambda k=6: (_ for _ in ()).throw(
            RuntimeError("Storage already accessed by another instance of Qdrant client")
        ),
    )

    with pytest.raises(qa_service.AskConfigError) as excinfo:
        qa_service.ask_question("roadmap sync")

    assert "vector store is unavailable" in str(excinfo.value).lower()


def test_ask_question_missing_collection_raises_config_error(monkeypatch):
    class FakeRetriever:
        def invoke(self, _query):
            raise RuntimeError("Collection microclub_knowledge not found")

    def fake_hybrid_retriever(k=6):
        return FakeRetriever()

    monkeypatch.setattr(qa_service, "get_llm", lambda: RunnableLambda(lambda _prompt: "ignored"))
    monkeypatch.setattr(qa_service, "get_hybrid_retriever", fake_hybrid_retriever)
    monkeypatch.setattr(
        qa_service,
        "build_rag_prompt_template",
        lambda: RunnableLambda(lambda data: data["question"]),
    )
    monkeypatch.setattr(
        qa_service,
        "_invoke_with_timeout",
        lambda chain, question, timeout_seconds=30: chain.invoke(question),
    )

    with pytest.raises(qa_service.AskConfigError) as excinfo:
        qa_service.ask_question("when is the next event?")

    assert "does not exist" in str(excinfo.value).lower()
