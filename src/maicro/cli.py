import argparse
import asyncio
import sys

from maicro.core.config import settings
from maicro.services.qa_service import AskError, ask_question


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
    except KeyboardInterrupt:
        print("Cancelled by user.")
        raise SystemExit(130)
    except AskError as exc:
        print(f"Error: {exc}")
        raise SystemExit(2) from exc


def ingest_main() -> None:
    """Ingest data from Discord from the command line."""

    parser = argparse.ArgumentParser(prog="maicro-ingest")
    parser.add_argument(
        "--limit",
        type=int,
        default=200,
        help="Max messages to fetch per Discord channel.",
    )
    args = parser.parse_args(sys.argv[1:])

    from maicro.core.ingestion import ingest_from_discord

    try:
        if not settings.DISCORD_BOT_TOKEN:
            print("Error: DISCORD_BOT_TOKEN not found in .env.")
            raise SystemExit(1)
        if not settings.discord_channel_id_list:
            print("Error: DISCORD_CHANNEL_IDS not found in .env.")
            raise SystemExit(1)
        if args.limit <= 0:
            print("Error: --limit must be a positive integer.")
            raise SystemExit(1)
        if not settings.GOOGLE_API_KEY:
            print(
                "Error: GOOGLE_API_KEY not found in .env. "
                "Ingestion embeddings currently use Google."
            )
            raise SystemExit(1)

        result = asyncio.run(ingest_from_discord(limit_per_channel=args.limit))
        status = "partial" if result.get("errors") else "ok"
        print(
            "Discord ingestion complete. "
            f"Status: {status}. Documents ingested: {result.get('total_documents', 0)}"
        )
        channels = result.get("channels") or {}
        errors = result.get("errors") or {}
        if channels:
            print(f"Per-channel counts: {channels}")
        if errors:
            print(f"Channel errors: {errors}")
            raise SystemExit(2)
    except Exception as exc:
        print(f"Error: {exc}")
        raise SystemExit(2) from exc
