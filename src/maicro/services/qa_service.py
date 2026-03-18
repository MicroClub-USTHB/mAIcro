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
_TEMPORAL_KEYWORDS_PATTERN = re.compile(
    r"\b(today|tomorrow|yesterday|this week|next week)\b", re.IGNORECASE
)

# Maximum messages fetched for "today's updates" — keeps the prompt bounded.
_CONTEXT_CHAR_BUDGET = 6_000   
_DOC_CHAR_LIMIT      = 1_200   
_TODAY_MESSAGES_LIMIT = 50


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
            f"{timeout_seconds}s. Please retry and check your LLM provider quota/connectivity."
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
            "Verify your provider API key(s) in the .env file."
        )

    return f"Request failed: {message}"


def _format_context(docs: list[Document]) -> str:
    if not docs:
        return "No relevant context retrieved."

    chunks = []
    total_chars = 0

    for i, doc in enumerate(docs, start=1):
        text = " ".join((doc.page_content or "").split())
        text = text[:_DOC_CHAR_LIMIT]

        metadata = doc.metadata or {}
        source = metadata.get("source") or metadata.get("channel_id") or "unknown"
        date = metadata.get("date") or metadata.get("timestamp") or "unknown"

        chunk = f"[{i}] source={source} | date={date}\\n{text}"

        if total_chars + len(chunk) > _CONTEXT_CHAR_BUDGET:
            logger.debug(
                "[context] Budget exhausted after %d/%d docs (%d chars used).",
                i - 1, len(docs), total_chars,
            )
            break

        chunks.append(chunk)
        total_chars += len(chunk)

    return "\\n\\n".join(chunks) if chunks else "No relevant context retrieved."


def _normalize_question(question: str) -> str:
    normalized = " ".join(question.strip().split())
    for pattern, replacement in _QUESTION_REWRITES:
        normalized = pattern.sub(replacement, normalized)
    return normalized

def _doc_key(doc: Document) -> tuple[str, str, str]:
    """Stable deduplication key for a retrieved document."""
    metadata = doc.metadata or {}
    message_id = str(metadata.get("message_id") or "")
    source = str(metadata.get("source") or "")
    content_fp = " ".join((doc.page_content or "").split())[:200]
    return (source, message_id, content_fp)

def _merge_docs(primary: list[Document], secondary: list[Document], limit: int) -> list[Document]:
    merged: list[Document] = []
    seen: set[tuple[str, str, str]] = set()

    for doc in primary + secondary:
        key = _doc_key(doc)
        if key in seen:
            continue
        seen.add(key)
        merged.append(doc)
        if len(merged) >= limit:
            break

    return merged


def _retrieve_with_rewrites(question: str, retriever, k: int = 6) -> list[Document]:
    normalized = _normalize_question(question)
    needs_rewrite = normalized.lower() != question.strip().lower()

    if not needs_rewrite:
        return retriever.invoke(question)

    with ThreadPoolExecutor(max_workers=2) as executor:
        future_primary = executor.submit(retriever.invoke, question)
        future_secondary = executor.submit(retriever.invoke, normalized)
        primary = future_primary.result()
        secondary = future_secondary.result()

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


def _build_discord_filter():
    """Return a Qdrant filter that restricts results to Discord messages."""
    from qdrant_client.http import models as qdrant_models

    return qdrant_models.Filter(
        must=[
            qdrant_models.FieldCondition(
                key="metadata.source",
                match=qdrant_models.MatchValue(value="discord"),
            )
        ]
    )


def _latest_discord_message() -> str | None:
    """Return the single most-recent Discord message using server-side ordering.

    Replaces the old full-scan approach: instead of pulling all points into
    Python memory and sorting there, we ask Qdrant to order by timestamp
    descending and return only the first record.  This is O(log N) on the
    server and transfers exactly one point over the wire.
    """
    from qdrant_client.http import models as qdrant_models

    vector_store = get_vector_store()
    client = vector_store.client
    collection_name = vector_store.collection_name

    # order_by with desc direction was introduced in Qdrant 1.8.
    # With limit=1 we fetch only the single latest point — no pagination needed.
    points, _ = client.scroll(
        collection_name=collection_name,
        scroll_filter=_build_discord_filter(),
        order_by=qdrant_models.OrderBy(
            key="metadata.timestamp",
            direction=qdrant_models.Direction.DESC,
        ),
        with_payload=True,
        with_vectors=False,
        limit=1,
    )

    if not points:
        return None

    payload = points[0].payload or {}
    metadata = payload.get("metadata") or {}
    author = metadata.get("author") or "unknown"
    timestamp = metadata.get("timestamp") or "unknown"
    channel_id = metadata.get("channel_id") or "unknown"
    text = str(payload.get("page_content") or "").strip() or "No text content."

    return (
        f"Latest Discord message:\n"
        f"- author: {author}\n"
        f"- timestamp: {timestamp}\n"
        f"- channel_id: {channel_id}\n"
        f"- content: {text}"
    )


def _today_discord_messages(reference_date) -> list[dict]:
    """Return today's Discord messages, sorted newest-first, via Qdrant ordering.

    Key changes vs. the old implementation:
    - Sorting is done by Qdrant (order_by DESC) — no in-process sort.
    - We stop fetching as soon as we've scrolled past today's date, so we
      never load the entire collection into memory.
    - Results are capped at _TODAY_MESSAGES_LIMIT to bound prompt size.
    """
    from qdrant_client.http import models as qdrant_models

    vector_store = get_vector_store()
    client = vector_store.client
    collection_name = vector_store.collection_name

    results: list[dict] = []
    next_offset = None

    while len(results) < _TODAY_MESSAGES_LIMIT:
        points, next_offset = client.scroll(
            collection_name=collection_name,
            scroll_filter=_build_discord_filter(),
            order_by=qdrant_models.OrderBy(
                key="metadata.timestamp",
                direction=qdrant_models.Direction.DESC,
            ),
            with_payload=True,
            with_vectors=False,
            # Fetch in pages of 64; small enough to stay lean, large enough to
            # avoid round-trip overhead on busy channels.
            limit=64,
            offset=next_offset,
        )

        if not points:
            break

        for point in points:
            payload = point.payload or {}
            metadata = payload.get("metadata") or {}
            timestamp_str = str(metadata.get("timestamp") or "")
            dt = _parse_iso_timestamp(timestamp_str)

            if dt is None:
                continue

            # Because we're iterating newest-first, the moment we see a point
            # older than today we can stop — everything after will be older too.
            if dt.date() < reference_date:
                return results

            if dt.date() == reference_date:
                results.append(payload)
                if len(results) >= _TODAY_MESSAGES_LIMIT:
                    return results

        if next_offset is None:
            break

    return results


def _answer_from_latest_message_with_llm(question: str, latest_message: str, llm) -> str:
    """Use the LLM to phrase an answer grounded in the latest Discord message."""
    prompt = (
        "You are answering a question about the latest Discord message.\n"
        "Use only the provided latest-message data and do not invent details.\n"
        "Keep the answer concise and natural.\n\n"
        f"User question: {question}\n\n"
        f"{latest_message}\n"
    )
    chain = RunnableLambda(lambda p: _extract_llm_content(llm.invoke(p)))
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
    chain = RunnableLambda(lambda p: _extract_llm_content(llm.invoke(p)))
    return _invoke_with_timeout(chain, prompt)


def _extract_llm_content(result) -> str:
    return result.content if hasattr(result, "content") else str(result)


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
            if latest:
                return latest

    try:
        llm = get_llm()
    except ConfigurationError as exc:
        raise AskConfigError(str(exc)) from exc

    try:
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
