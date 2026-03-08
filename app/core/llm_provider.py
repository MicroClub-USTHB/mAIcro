from app.core.config import settings


class ConfigurationError(ValueError):
    """Raised when model providers are misconfigured."""


def get_llm():
    provider = settings.LLM_PROVIDER.lower().strip()
    if provider != "google":
        raise ConfigurationError(
            "Only Gemini is supported in this build. Set LLM_PROVIDER=google in .env."
        )

    from langchain_google_genai import ChatGoogleGenerativeAI

    if not settings.GOOGLE_API_KEY:
        raise ConfigurationError("GOOGLE_API_KEY not found in .env.")

    model_name = settings.MODEL_NAME or settings.GOOGLE_MODEL_NAME
    return ChatGoogleGenerativeAI(
        model=model_name,
        google_api_key=settings.GOOGLE_API_KEY,
        temperature=0,
    )

def get_embeddings():
    from langchain_google_genai import GoogleGenerativeAIEmbeddings

    if not settings.GOOGLE_API_KEY:
        raise ConfigurationError(
            "GOOGLE_API_KEY not found in .env. "
            "Gemini embeddings require a valid Google API key."
        )

    return GoogleGenerativeAIEmbeddings(
        model="models/gemini-embedding-001",
        google_api_key=settings.GOOGLE_API_KEY
    )

