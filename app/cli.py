"""CLI entrypoints for mAIcro."""

import os
import sys

from app.core.config import settings
from app.services.qa_service import AskError, ask_question


def ask_main() -> None:
    """Ask mAIcro a question from the command line."""
    if len(sys.argv) > 1:
        question = " ".join(sys.argv[1:])
    else:
        question = input("Ask mAIcro: ")

    provider = settings.LLM_PROVIDER.lower().strip()
    if provider == "anthropic" and not settings.ANTHROPIC_API_KEY:
        print("Error: ANTHROPIC_API_KEY not found in .env. Please set it to run.")
        raise SystemExit(1)

    if provider == "google" and not settings.GOOGLE_API_KEY:
        print("Error: GOOGLE_API_KEY not found in .env. Please set it to run.")
        raise SystemExit(1)

    if provider == "groq" and not settings.GROQ_API_KEY:
        print("Error: GROQ_API_KEY not found in .env. Please set it to run.")
        raise SystemExit(1)

    if provider not in {"google", "anthropic", "groq"}:
        print("Error: LLM_PROVIDER must be 'google', 'anthropic', or 'groq'.")
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
        print(f"Error: {exc}")
        raise SystemExit(2) from exc
