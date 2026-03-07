import sys

from app.core.config import settings
from app.services.qa_service import AskError, ask_question

if __name__ == "__main__":
    if len(sys.argv) > 1:
        question = " ".join(sys.argv[1:])
    else:
        question = input("Ask mAIcro: ")
        
    provider = settings.LLM_PROVIDER.lower().strip()
    if provider == "anthropic" and not settings.ANTHROPIC_API_KEY:
        print("Error: ANTHROPIC_API_KEY not found in .env. Please set it to run.")
        sys.exit(1)

    if provider == "google" and not settings.GOOGLE_API_KEY:
        print("Error: GOOGLE_API_KEY not found in .env. Please set it to run.")
        sys.exit(1)

    if provider == "groq" and not settings.GROQ_API_KEY:
        print("Error: GROQ_API_KEY not found in .env. Please set it to run.")
        sys.exit(1)

    if provider not in {"google", "anthropic", "groq"}:
        print("Error: LLM_PROVIDER must be 'google', 'anthropic', or 'groq'.")
        sys.exit(1)

    if not settings.GOOGLE_API_KEY:
        print(
            "Error: GOOGLE_API_KEY not found in .env. "
            "Embeddings still use Google in the current setup."
        )
        sys.exit(1)
        
    try:
        answer = ask_question(question)
        print(f"\nAnswer: {answer}")
    except AskError as exc:
        print(f"Error: {exc}")
        sys.exit(2)
