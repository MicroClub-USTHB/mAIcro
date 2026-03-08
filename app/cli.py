"""CLI entrypoints for mAIcro."""

import json
import sys
import urllib.error
import urllib.request

from app.core.config import settings
from app.services.qa_service import AskError, ask_question


def ask_main() -> None:
    """Ask mAIcro a question from the command line."""
    if len(sys.argv) > 1:
        question = " ".join(sys.argv[1:])
    else:
        question = input("Ask mAIcro: ")

    provider = settings.LLM_PROVIDER.lower().strip()
    if provider != "google":
        print("Error: only Gemini is supported. Set LLM_PROVIDER=google in .env.")
        raise SystemExit(1)

    if not settings.GOOGLE_API_KEY:
        print("Error: GOOGLE_API_KEY not found in .env. Please set it to run.")
        raise SystemExit(1)

    try:
        answer = ask_question(question)
        print(f"\nAnswer: {answer}")
    except AskError as exc:
        print(f"Error: {exc}")
        raise SystemExit(2) from exc


def ingest_main() -> None:
    """Ingest default announcements data from the command line."""
    from app.core.ingestion import ingest_from_json

    if not settings.GOOGLE_API_KEY:
        print(
            "Error: GOOGLE_API_KEY not found in .env. "
            "Ingestion embeddings currently use Google."
        )
        raise SystemExit(1)

    try:
        count = ingest_from_json("data/announcements.json")
        print(f"Ingestion complete. Documents ingested: {count}")
    except Exception as exc:
        message = str(exc)
        if "already accessed by another instance of Qdrant client" in message:
            # If the API server already owns the local_qdrant lock, delegate ingestion to it.
            try:
                req = urllib.request.Request(
                    "http://localhost:8000/api/v1/ingest",
                    data=json.dumps({"path": "data/announcements.json"}).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=60) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                print(
                    "Ingestion complete via API fallback. "
                    f"Documents ingested: {payload.get('documents_ingested', 0)}"
                )
                return
            except urllib.error.URLError:
                print(
                    "Error: local_qdrant is locked by another process and API fallback failed. "
                    "Start the API server (`uv run uvicorn main:app --reload`) or stop the other process."
                )
                raise SystemExit(2) from exc

        print(f"Error: {exc}")
        raise SystemExit(2) from exc
