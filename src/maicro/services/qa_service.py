"""Question-answering service built on top of retrieval-augmented generation."""

import logging
import re
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from datetime import datetime, timezone

from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnableLambda, RunnablePassthrough

from maicro.core.config import settings
from maicro.core.hybrid_search import get_hybrid_retriever
from maicro.core.llm_provider import ConfigurationError, get_llm
from maicro.core.prompt_template import build_rag_prompt_template
from maicro.core.vector_store import get_vector_store

logger = logging.getLogger(__name__)


class AskError(Exception):
    """Raised when asking the LLM fails with a user-actionable error."""


class AskConfigError(AskError):
    """Raised when server-side AI providers are not configured correctly."""


_ASK_TIMEOUT_SECONDS = 30
_RECENCY_MESSAGE_PATTERN = re.compile(
    r"\b(last|latest|most recent|newest)\b.*\b(message|msg|post)\b|\bwhat(?:'s| is)\s+the\s+last\s+message\b",
    re.IGNORECASE,
)
_TODAY_UPDATES_PATTERN = re.compile(
    r"\b(today)\b.*\b(update|updates|plan|agenda|have|happening)\b|\bwhat(?:'s|s)?\b.*\b(have|happening)\b.*\btoday\b",
    re.IGNORECASE,
)
_QUESTION_REWRITES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bwhats\b", re.IGNORECASE), "what is"),
    (re.compile(r"\bwanna\b", re.IGNORECASE), "want to"),
    (re.compile(r"\bgonna\b", re.IGNORECASE), "going to"),
    (re.compile(r"\bthe\s+we\s+have\b", re.IGNORECASE), "do we have"),
]
_TEMPORAL_KEYWORDS_PATTERN = re.compile(r"\b(today|tomorrow|yesterday|this week|next week)\b", re.IGNORECASE)


def _is_missing_collection_error(message: str) -> bool:
    if not message:
        return False
    lowered = message.lower()
    collection = settings.COLLECTION_NAME.lower()
    if collection not in lowered:
        return False
    return any(needle in lowered for needle in ("doesn't exist", "does not exist", "not found"))


def _invoke_with_timeout(chain, question: str, timeout_seconds: int = _ASK_TIMEOUT_SECONDS) -> str:
    """Run model invocation with a hard timeout to avoid long-hanging requests."""
    executor = ThreadPoolExecutor(max_workers=1)
    future = executor.submit(chain.invoke, question)
    try:
        return future.result(timeout=timeout_seconds)
    except KeyboardInterrupt as exc:
        future.cancel()
        raise AskError("Request cancelled by user.") from exc
    except FutureTimeoutError as exc:
        future.cancel()
        raise AskError(
            "LLM request timed out after "
            f"{timeout_seconds}s. Please retry and check Gemini API quota/connectivity."
        ) from exc
    finally:
        executor.shutdown(wait=False, cancel_futures=True)


def _format_llm_error(exc: Exception) -> str:
    """Convert provider errors into short messages suitable for API/CLI users."""
    message = str(exc)
    lowered = message.lower()

    if "resource_exhausted" in lowered or "quota" in lowered or "429" in lowered:
        return (
            "LLM quota/rate limit was exceeded. "
            "Check your provider billing/quota, wait a bit, then retry."
        )

    if "api key" in lowered or "permission denied" in lowered or "unauthorized" in lowered:
        return (
            "Invalid API credentials. "
            "Verify GOOGLE_API_KEY in your .env file."
        )

    return f"Request failed: {message}"


def _format_context(docs: list[Document]) -> str:
    """Render retrieved docs into concise, traceable snippets for the prompt."""
    if not docs:
        return "No relevant context retrieved."

    chunks = []
    for i, doc in enumerate(docs, start=1):
        text = " ".join((doc.page_content or "").split())
        text = text[:1200]

        metadata = doc.metadata or {}
        source = metadata.get("source") or metadata.get("channel_id") or "unknown"
        date = metadata.get("date") or metadata.get("timestamp") or "unknown"

        chunks.append(f"[{i}] source={source} | date={date}\\n{text}")

    return "\\n\\n".join(chunks)


def _normalize_question(question: str) -> str:
    normalized = " ".join(question.strip().split())
    for pattern, replacement in _QUESTION_REWRITES:
        normalized = pattern.sub(replacement, normalized)
    return normalized


def _merge_docs(primary: list[Document], secondary: list[Document], limit: int) -> list[Document]:
    merged: list[Document] = []
    seen: set[tuple[str, str, str]] = set()

    def _key(doc: Document) -> tuple[str, str, str]:
        metadata = doc.metadata or {}
        return (
            str(metadata.get("source", "")),
            str(metadata.get("message_id", "")),
            (doc.page_content or "")[:160],
        )

    for doc in primary + secondary:
        key = _key(doc)
        if key in seen:
            continue
        seen.add(key)
        merged.append(doc)
        if len(merged) >= limit:
            break

    return merged


def _retrieve_with_rewrites(question: str, retriever, k: int = 6) -> list[Document]:
    normalized = _normalize_question(question)
    primary = retriever.invoke(question)
    if normalized.lower() == question.strip().lower():
        return primary
    secondary = retriever.invoke(normalized)
    return _merge_docs(primary, secondary, limit=k)


def _augment_temporal_question(question: str) -> str:
    if not _TEMPORAL_KEYWORDS_PATTERN.search(question):
        return question
    ref_date = datetime.now(timezone.utc).date().isoformat()
    return f"{question}\nReference date (UTC): {ref_date}"


def _is_recency_message_query(question: str) -> bool:
    return bool(_RECENCY_MESSAGE_PATTERN.search(question.strip()))


def _is_today_updates_query(question: str) -> bool:
    return bool(_TODAY_UPDATES_PATTERN.search(question.strip()))


def _parse_iso_timestamp(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _latest_discord_message() -> str | None:
    """Return a deterministic response for the latest Discord message in storage."""
    from qdrant_client.http import models as qdrant_models

    vector_store = get_vector_store()
    client = vector_store.client
    collection_name = vector_store.collection_name

    next_offset = None
    latest_payload = None
    latest_dt = None

    while True:
        points, next_offset = client.scroll(
            collection_name=collection_name,
            scroll_filter=qdrant_models.Filter(
                must=[
                    qdrant_models.FieldCondition(
                        key="metadata.source",
                        match=qdrant_models.MatchValue(value="discord"),
                    )
                ]
            ),
            with_payload=True,
            with_vectors=False,
            limit=256,
            offset=next_offset,
        )

        for point in points:
            payload = point.payload or {}
            metadata = payload.get("metadata") or {}
            timestamp = str(metadata.get("timestamp") or "")
            dt = _parse_iso_timestamp(timestamp)
            if dt is None:
                continue
            if latest_dt is None or dt > latest_dt:
                latest_dt = dt
                latest_payload = payload

        if next_offset is None:
            break

    if not latest_payload:
        return None

    metadata = latest_payload.get("metadata") or {}
    author = metadata.get("author") or "unknown"
    timestamp = metadata.get("timestamp") or "unknown"
    channel_id = metadata.get("channel_id") or "unknown"
    text = str(latest_payload.get("page_content") or "").strip()
    if not text:
        text = "No text content."

    return (
        f"Latest Discord message:\n"
        f"- author: {author}\n"
        f"- timestamp: {timestamp}\n"
        f"- channel_id: {channel_id}\n"
        f"- content: {text}"
    )


def _collect_discord_messages_sorted() -> list[tuple[datetime, dict]]:
    from qdrant_client.http import models as qdrant_models

    vector_store = get_vector_store()
    client = vector_store.client
    collection_name = vector_store.collection_name

    next_offset = None
    items: list[tuple[datetime, dict]] = []

    while True:
        points, next_offset = client.scroll(
            collection_name=collection_name,
            scroll_filter=qdrant_models.Filter(
                must=[
                    qdrant_models.FieldCondition(
                        key="metadata.source",
                        match=qdrant_models.MatchValue(value="discord"),
                    )
                ]
            ),
            with_payload=True,
            with_vectors=False,
            limit=256,
            offset=next_offset,
        )

        for point in points:
            payload = point.payload or {}
            metadata = payload.get("metadata") or {}
            timestamp = str(metadata.get("timestamp") or "")
            dt = _parse_iso_timestamp(timestamp)
            if dt is None:
                continue
            items.append((dt, payload))

        if next_offset is None:
            break

    items.sort(key=lambda x: x[0], reverse=True)
    return items


def _today_discord_messages(reference_date) -> list[dict]:
    return [
        payload
        for dt, payload in _collect_discord_messages_sorted()
        if dt.date() == reference_date
    ]


def _answer_from_latest_message_with_llm(question: str, latest_message: str, llm) -> str:
    """Use the LLM to phrase an answer grounded in the latest Discord message."""
    prompt = (
        "You are answering a question about the latest Discord message.\n"
        "Use only the provided latest-message data and do not invent details.\n"
        "Keep the answer concise and natural.\n\n"
        f"User question: {question}\n\n"
        f"{latest_message}\n"
    )
    chain = RunnableLambda(lambda p: llm.invoke(p).content)
    return _invoke_with_timeout(chain, prompt)


def _answer_today_updates_with_llm(question: str, messages: list[dict], llm, reference_date: str) -> str:
    rows = []
    for item in messages[:8]:
        metadata = item.get("metadata") or {}
        rows.append(
            f"- {metadata.get('timestamp', 'unknown')} | {metadata.get('author', 'unknown')}: "
            f"{str(item.get('page_content') or '').strip()}"
        )
    prompt = (
        "You are answering a question about today's Discord updates.\n"
        "Use only the provided message list and do not invent details.\n"
        f"Reference date (UTC): {reference_date}\n\n"
        f"User question: {question}\n\n"
        "Messages:\n"
        + "\n".join(rows)
    )
    chain = RunnableLambda(lambda p: llm.invoke(p).content)
    return _invoke_with_timeout(chain, prompt)


def ask_question(question: str) -> str:
    """Answer a user question from the configured RAG pipeline."""
    if _is_today_updates_query(question):
        try:
            llm = get_llm()
            ref_date = datetime.now(timezone.utc).date()
            today_messages = _today_discord_messages(reference_date=ref_date)
            if today_messages:
                return _answer_today_updates_with_llm(
                    question=question,
                    messages=today_messages,
                    llm=llm,
                    reference_date=ref_date.isoformat(),
                )
            latest = _latest_discord_message()
            if latest:
                return _answer_from_latest_message_with_llm(question, latest, llm)
        except Exception:
            pass

    if _is_recency_message_query(question):
        latest = None
        try:
            latest = _latest_discord_message()
            if latest:
                llm = get_llm()
                return _answer_from_latest_message_with_llm(question, latest, llm)
        except Exception:
            # Fall back to deterministic latest message, then standard RAG path.
            if latest:
                return latest

    try:
        llm = get_llm()
    except ConfigurationError as exc:
        raise AskConfigError(str(exc)) from exc

    try:
        # Use hybrid retriever
        retriever = get_hybrid_retriever(k=6)
    except ConfigurationError as exc:
        raise AskConfigError(str(exc)) from exc
    except Exception as exc:
        message = str(exc)
        lowered = message.lower()
        is_lock = "already accessed by another instance of qdrant client" in lowered
        is_connection = any(
            needle in lowered
            for needle in (
                "connection refused",
                "failed to establish a new connection",
                "max retries exceeded",
                "connection error",
                "connectionerror",
                "timed out",
                "timeout",
                "name or service not known",
                "temporary failure in name resolution",
            )
        )
        if is_lock or is_connection:
            raise AskConfigError(
                "Vector store is unavailable. Start Qdrant and ingest Discord data first."
            ) from exc
        raise AskConfigError(f"Vector store initialization failed: {message}") from exc

    prompt = build_rag_prompt_template()
    normalized_question = _normalize_question(question)
    effective_question = _augment_temporal_question(normalized_question)

    def _build_chain(model):
        def _debug_retrieve(q):
            docs = _retrieve_with_rewrites(q, retriever, k=6)
            logger.info(f"[DEBUG] Retrieved {len(docs)} documents for question: {q}")
            for i, doc in enumerate(docs):
                logger.info(f"[DEBUG] Doc {i}: {doc.page_content[:200]}... | metadata: {doc.metadata}")
            return docs
        
        return (
            {
                "context": RunnableLambda(lambda q: _debug_retrieve(q))
                | RunnableLambda(_format_context),
                "question": RunnableLambda(lambda _q: effective_question),
            }
            | prompt
            | model
            | StrOutputParser()
        )

    chain = _build_chain(llm)

    try:
        return _invoke_with_timeout(chain, question)
    except Exception as exc:
        if _is_missing_collection_error(str(exc)):
            raise AskConfigError(
                "Vector store is not initialized yet. "
                f"Qdrant collection `{settings.COLLECTION_NAME}` does not exist. "
                "Ingest Discord data first (POST /api/v1/ingest/discord)."
            ) from exc
        raise AskError(_format_llm_error(exc)) from exc

