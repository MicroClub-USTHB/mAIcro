from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_anthropic import ChatAnthropic
from app.core.config import settings

def get_llm():
    provider = settings.LLM_PROVIDER.lower().strip()

    if provider == "anthropic":
        if not settings.ANTHROPIC_API_KEY:
            raise ValueError("ANTHROPIC_API_KEY not found in .env.")

        model_name = settings.MODEL_NAME or settings.ANTHROPIC_MODEL_NAME
        return ChatAnthropic(
            model=model_name,
            anthropic_api_key=settings.ANTHROPIC_API_KEY,
            temperature=0,
        )

    if provider == "google":
        if not settings.GOOGLE_API_KEY:
            raise ValueError("GOOGLE_API_KEY not found in .env.")

        model_name = settings.MODEL_NAME or settings.GOOGLE_MODEL_NAME
        return ChatGoogleGenerativeAI(
            model=model_name,
            google_api_key=settings.GOOGLE_API_KEY,
            temperature=0,
        )

    raise ValueError("Unsupported LLM_PROVIDER. Use 'google' or 'anthropic'.")

def get_embeddings():
    if not settings.GOOGLE_API_KEY:
        raise ValueError(
            "GOOGLE_API_KEY not found in .env. "
            "Current embedding backend uses Google embeddings."
        )

    return GoogleGenerativeAIEmbeddings(
        model="models/gemini-embedding-001",
        google_api_key=settings.GOOGLE_API_KEY
    )

