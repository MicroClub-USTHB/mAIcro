import asyncio
import importlib

import httpx

import api.routes as routes
import main as main_module
from core.config import settings
from services.qa_service import AskError
from main import app


def request(method: str, path: str, app_instance=None, **kwargs):
    async def _send():
        transport = httpx.ASGITransport(app=app_instance or app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.request(method, path, **kwargs)

    return asyncio.run(_send())


def build_app_with_cors(monkeypatch, origins: str):
    monkeypatch.setattr(settings, "CORS_ORIGINS", origins)
    return importlib.reload(main_module).app


def test_health_endpoint_returns_ok():
    res = request("GET", "/api/v1/health")

    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert "llm_provider" in body


def test_ask_rejects_empty_question():
    res = request("POST", "/api/v1/ask", json={"question": "   "})

    assert res.status_code == 400
    assert "cannot be empty" in res.json()["detail"].lower()


def test_ask_success(monkeypatch):
    monkeypatch.setattr(routes, "ask_question", lambda q: "answer: " + q)

    res = request("POST", "/api/v1/ask", json={"question": "hello"})

    assert res.status_code == 200
    assert res.json() == {"question": "hello", "answer": "answer: hello"}


def test_ask_error_is_mapped_to_502(monkeypatch):
    def _raise(_q):
        raise AskError("upstream failed")

    monkeypatch.setattr(routes, "ask_question", _raise)

    res = request("POST", "/api/v1/ask", json={"question": "hello"})

    assert res.status_code == 502
    assert "upstream failed" in res.json()["detail"]


def test_ingest_discord_requires_token(monkeypatch):
    monkeypatch.setattr(routes.settings, "DISCORD_BOT_TOKEN", None)
    monkeypatch.setattr(routes.settings, "DISCORD_CHANNEL_IDS", "123")

    res = request("POST", "/api/v1/ingest/discord")

    assert res.status_code == 400
    assert "DISCORD_BOT_TOKEN" in res.json()["detail"]


def test_ingest_discord_partial_response(monkeypatch):
    monkeypatch.setattr(routes.settings, "DISCORD_BOT_TOKEN", "x")
    monkeypatch.setattr(routes.settings, "DISCORD_CHANNEL_IDS", "123")

    async def _fake_ingest():
        return {
            "channels": {"123": 5},
            "errors": {"456": "missing access"},
            "total_documents": 5,
        }

    import core.ingestion as ingestion

    monkeypatch.setattr(ingestion, "ingest_from_discord", _fake_ingest)

    res = request("POST", "/api/v1/ingest/discord")

    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "partial"
    assert body["documents_ingested"] == 5
    assert body["details"]["channels"] == {"123": 5}
    assert body["details"]["errors"] == {"456": "missing access"}


def test_cors_preflight_allows_configured_frontend_origin(monkeypatch):
    cors_app = build_app_with_cors(
        monkeypatch, "http://localhost:3000,https://app.example.com"
    )

    res = request(
        "OPTIONS",
        "/api/v1/ask",
        app_instance=cors_app,
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    assert res.status_code == 200
    assert res.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert "POST" in res.headers["access-control-allow-methods"]


def test_cors_preflight_rejects_unconfigured_origin(monkeypatch):
    cors_app = build_app_with_cors(monkeypatch, "http://localhost:3000")

    res = request(
        "OPTIONS",
        "/api/v1/ask",
        app_instance=cors_app,
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
        },
    )

    assert res.status_code == 400
    assert "access-control-allow-origin" not in res.headers
