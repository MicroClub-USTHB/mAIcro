import pytest
from core.config import settings

@pytest.fixture(autouse=True)
def mock_env_vars(monkeypatch):
    """Provide dummy environment variables for all tests to bypass strict Cloud-only checks."""
    monkeypatch.setattr(settings, "QDRANT_URL", "https://dummy.qdrant.io:6333")
    monkeypatch.setattr(settings, "QDRANT_API_KEY", "dummy-api-key")
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "dummy-gemini-key")
    monkeypatch.setattr(settings, "DISCORD_BOT_TOKEN", "dummy-discord-token")
    monkeypatch.setattr(settings, "DISCORD_CHANNEL_IDS", "123456789")
