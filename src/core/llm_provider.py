from __future__ import annotations

import logging
import random
import time
from typing import Optional

from langchain_core.runnables import RunnableLambda

from core.config import settings


class ConfigurationError(ValueError):
    """Raised when model providers are misconfigured."""


_LOGGER = logging.getLogger(__name__)


class RateLimitExceeded(Exception):
    """Raised when the primary provider is rate-limited after retries."""

    def __init__(self, last_exc: Exception):
        super().__init__(str(last_exc))
        self.last_exc = last_exc


def _resolve_model_name(*, secondary: bool) -> str:
    if secondary and settings.SECONDARY_MODEL_NAME:
        return settings.SECONDARY_MODEL_NAME
    return settings.MODEL_NAME or settings.GOOGLE_MODEL_NAME


def _build_google_llm(*, secondary: bool):
    from langchain_google_genai import ChatGoogleGenerativeAI

    api_key = (
        settings.SECONDARY_GEMINI_API_KEY if secondary else settings.GEMINI_API_KEY
    )
    if not api_key:
        missing_key = "SECONDARY_GEMINI_API_KEY" if secondary else "GEMINI_API_KEY"
        raise ConfigurationError(f"{missing_key} not found in .env.")

    model_name = _resolve_model_name(secondary=secondary)
    return ChatGoogleGenerativeAI(
        model=model_name,
        google_api_key=api_key,
        temperature=0,
    )


def _extract_status_code(exc: Exception) -> Optional[int]:
    for attr in ("status_code", "code"):
        value = getattr(exc, attr, None)
        if isinstance(value, int):
            return value
        if isinstance(value, str):
            try:
                return int(value)
            except ValueError:
                pass
    response = getattr(exc, "response", None)
    if response is not None:
        code = getattr(response, "status_code", None)
        if isinstance(code, int):
            return code
        if isinstance(code, str):
            try:
                return int(code)
            except ValueError:
                pass
    return None


def _is_rate_limit_error(exc: Exception) -> bool:
    code = _extract_status_code(exc)
    return code == 429


def _sleep_with_exponential_backoff(attempt: int) -> None:
    base = min(
        settings.LLM_BACKOFF_BASE_DELAY_SECONDS * (2 ** (attempt - 1)),
        settings.LLM_BACKOFF_MAX_DELAY_SECONDS,
    )
    jitter = random.uniform(0, 0.2)
    time.sleep(base + jitter)


def _invoke_with_rate_limit_retries(llm, prompt: str):
    for attempt in range(1, settings.LLM_MAX_PRIMARY_ATTEMPTS + 1):
        try:
            return llm.invoke(prompt)
        except Exception as exc:
            if not _is_rate_limit_error(exc):
                raise
            if attempt >= settings.LLM_MAX_PRIMARY_ATTEMPTS:
                raise RateLimitExceeded(exc) from exc
            _sleep_with_exponential_backoff(attempt)


def _build_fallback_router(primary_llm, secondary_llm):
    def _invoke(prompt: str):
        try:
            return _invoke_with_rate_limit_retries(primary_llm, prompt)
        except RateLimitExceeded:
            _LOGGER.warning(
                "Primary Gemini model rate-limited after %s attempts; switching to fallback.",
                settings.LLM_MAX_PRIMARY_ATTEMPTS,
            )
            return secondary_llm.invoke(prompt)

    return RunnableLambda(_invoke)


def get_llm():
    provider = settings.LLM_PROVIDER.lower().strip()
    if provider != "google":
        raise ConfigurationError(
            "Only Gemini is supported in this build. Set LLM_PROVIDER=google in .env."
        )

    primary_llm = _build_google_llm(secondary=False)
    if not settings.LLM_FALLBACK_ENABLED:
        return primary_llm
    if not settings.SECONDARY_LLM_PROVIDER or not settings.SECONDARY_GEMINI_API_KEY:
        raise ConfigurationError(
            "Fallback enabled but SECONDARY_LLM_PROVIDER or SECONDARY_GEMINI_API_KEY is missing."
        )

    secondary_llm = _build_google_llm(secondary=True)
    return _build_fallback_router(primary_llm, secondary_llm)


def get_embeddings():
    from langchain_google_genai import GoogleGenerativeAIEmbeddings

    if not settings.GEMINI_API_KEY:
        raise ConfigurationError(
            "GEMINI_API_KEY not found in .env. "
            "Gemini embeddings require a valid Google API key."
        )

    return GoogleGenerativeAIEmbeddings(
        model="models/gemini-embedding-001", google_api_key=settings.GEMINI_API_KEY
    )
