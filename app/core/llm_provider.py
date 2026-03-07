from app.core.config import settings


class ConfigurationError(ValueError):
    """Raised when model providers are misconfigured."""


def get_llm():
    provider = settings.LLM_PROVIDER.lower().strip()

    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        if not settings.ANTHROPIC_API_KEY:
            raise ConfigurationError("ANTHROPIC_API_KEY not found in .env.")

        model_name = settings.MODEL_NAME or settings.ANTHROPIC_MODEL_NAME
        return ChatAnthropic(
            model=model_name,
            anthropic_api_key=settings.ANTHROPIC_API_KEY,
            temperature=0,
        )

    if provider == "google":
        from langchain_google_genai import ChatGoogleGenerativeAI

        if not settings.GOOGLE_API_KEY:
            raise ConfigurationError("GOOGLE_API_KEY not found in .env.")

        model_name = settings.MODEL_NAME or settings.GOOGLE_MODEL_NAME
        return ChatGoogleGenerativeAI(
            model=model_name,
            google_api_key=settings.GOOGLE_API_KEY,
            temperature=0,
        )

    if provider == "groq":
        from langchain_groq import ChatGroq

        if not settings.GROQ_API_KEY:
            raise ConfigurationError("GROQ_API_KEY not found in .env.")

        model_name = settings.MODEL_NAME or settings.GROQ_MODEL_NAME
        return ChatGroq(
            model=model_name,
            api_key=settings.GROQ_API_KEY,
            temperature=0,
        )

    raise ConfigurationError("Unsupported LLM_PROVIDER. Use 'google', 'anthropic', or 'groq'.")

def get_embeddings():
    from langchain_google_genai import GoogleGenerativeAIEmbeddings

    if not settings.GOOGLE_API_KEY:
        raise ConfigurationError(
            "GOOGLE_API_KEY not found in .env. "
            "Embeddings are currently configured to use Google embeddings even when "
            "LLM_PROVIDER is set to another provider (for example, groq)."
        )

    return GoogleGenerativeAIEmbeddings(
        model="models/gemini-embedding-001",
        google_api_key=settings.GOOGLE_API_KEY
    )

