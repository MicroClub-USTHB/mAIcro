import types

import pytest

from app.core import llm_provider


@pytest.fixture
def restore_settings():
    original_provider = llm_provider.settings.LLM_PROVIDER
    original_google_key = llm_provider.settings.GOOGLE_API_KEY
    original_model_name = llm_provider.settings.MODEL_NAME
    original_google_model_name = llm_provider.settings.GOOGLE_MODEL_NAME
    try:
        yield
    finally:
        llm_provider.settings.LLM_PROVIDER = original_provider
        llm_provider.settings.GOOGLE_API_KEY = original_google_key
        llm_provider.settings.MODEL_NAME = original_model_name
        llm_provider.settings.GOOGLE_MODEL_NAME = original_google_model_name


def test_get_llm_rejects_non_google_provider(restore_settings):
    llm_provider.settings.LLM_PROVIDER = "groq"
    llm_provider.settings.GOOGLE_API_KEY = "dummy"

    with pytest.raises(llm_provider.ConfigurationError, match="Only Gemini"):
        llm_provider.get_llm()


def test_get_llm_requires_google_api_key(restore_settings):
    llm_provider.settings.LLM_PROVIDER = "google"
    llm_provider.settings.GOOGLE_API_KEY = None

    with pytest.raises(llm_provider.ConfigurationError, match="GOOGLE_API_KEY"):
        llm_provider.get_llm()


def test_get_llm_builds_google_client(restore_settings, monkeypatch):
    captured = {}

    class FakeChatGoogleGenerativeAI:
        def __init__(self, model, google_api_key, temperature):
            captured["model"] = model
            captured["google_api_key"] = google_api_key
            captured["temperature"] = temperature

    fake_mod = types.SimpleNamespace(ChatGoogleGenerativeAI=FakeChatGoogleGenerativeAI)
    monkeypatch.setattr(llm_provider, "settings", llm_provider.settings)
    monkeypatch.setitem(__import__("sys").modules, "langchain_google_genai", fake_mod)

    llm_provider.settings.LLM_PROVIDER = "google"
    llm_provider.settings.GOOGLE_API_KEY = "test-key"
    llm_provider.settings.MODEL_NAME = None
    llm_provider.settings.GOOGLE_MODEL_NAME = "gemini-test"

    client = llm_provider.get_llm()

    assert isinstance(client, FakeChatGoogleGenerativeAI)
    assert captured == {
        "model": "gemini-test",
        "google_api_key": "test-key",
        "temperature": 0,
    }


def test_get_embeddings_requires_google_api_key(restore_settings):
    llm_provider.settings.GOOGLE_API_KEY = None

    with pytest.raises(llm_provider.ConfigurationError, match="Gemini embeddings"):
        llm_provider.get_embeddings()
