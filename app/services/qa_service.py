"""Question-answering service built on top of retrieval-augmented generation."""

import json
import re
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from functools import lru_cache
from pathlib import Path

from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnableLambda, RunnablePassthrough

from app.core.llm_provider import ConfigurationError, get_llm
from app.core.prompt_template import build_rag_prompt_template
from app.core.vector_store import get_vector_store


class AskError(Exception):
    """Raised when asking the LLM fails with a user-actionable error."""


class AskConfigError(AskError):
    """Raised when server-side AI providers are not configured correctly."""


_ASK_TIMEOUT_SECONDS = 30


def _invoke_with_timeout(chain, question: str, timeout_seconds: int = _ASK_TIMEOUT_SECONDS) -> str:
    """Run model invocation with a hard timeout to avoid long-hanging requests."""
    executor = ThreadPoolExecutor(max_workers=1)
    future = executor.submit(chain.invoke, question)
    try:
        return future.result(timeout=timeout_seconds)
    except FutureTimeoutError as exc:
        future.cancel()
        raise AskError(
            "LLM request timed out after "
            f"{timeout_seconds}s. Please retry and check Gemini API quota/connectivity."
        ) from exc
    finally:
        executor.shutdown(wait=False, cancel_futures=True)


@lru_cache(maxsize=1)
def _load_local_announcements_docs() -> list[Document]:
    """Load local announcements as a fallback knowledge source."""
    data_path = Path(__file__).resolve().parents[2] / "data" / "announcements.json"
    if not data_path.exists():
        raise AskConfigError(f"Fallback data file not found: {data_path}")

    try:
        raw = json.loads(data_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise AskConfigError(f"Invalid JSON in fallback data file: {data_path}") from exc

    docs: list[Document] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "Untitled")
        content = str(item.get("content") or "")
        date = str(item.get("date") or "unknown")

        docs.append(
            Document(
                page_content=f"{title}\n{content}".strip(),
                metadata={
                    "source": "data/announcements.json",
                    "date": date,
                    "title": title,
                },
            )
        )

    if not docs:
        raise AskConfigError("Fallback data file contains no usable documents.")

    return docs


def _tokenize(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def _fallback_keyword_retrieve(question: str, k: int = 3) -> list[Document]:
    """Very small lexical retriever used when vector embeddings are unavailable."""
    docs = _load_local_announcements_docs()
    q_tokens = _tokenize(question)

    scored: list[tuple[int, Document]] = []
    for doc in docs:
        doc_tokens = _tokenize(doc.page_content)
        score = len(q_tokens & doc_tokens)
        scored.append((score, doc))

    scored.sort(key=lambda x: x[0], reverse=True)
    top = [doc for score, doc in scored if score > 0][:k]
    if top:
        return top

    return [doc for _, doc in scored[:k]]


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


def ask_question(question: str) -> str:
    """Answer a user question from the configured RAG pipeline."""
    try:
        llm = get_llm()
    except ConfigurationError as exc:
        raise AskConfigError(str(exc)) from exc

    try:
        vector_store = get_vector_store()
        retriever = vector_store.as_retriever(search_kwargs={"k": 3})
    except ConfigurationError as exc:
        # Allow non-Google LLM setups to run using local lexical retrieval.
        if "GOOGLE_API_KEY" in str(exc):
            retriever = RunnableLambda(lambda q: _fallback_keyword_retrieve(q, k=3))
        else:
            raise AskConfigError(str(exc)) from exc
    except Exception as exc:
        message = str(exc)
        # Qdrant local mode uses a file lock and can fail when another process has opened it.
        if "already accessed by another instance of Qdrant client" in message:
            retriever = RunnableLambda(lambda q: _fallback_keyword_retrieve(q, k=3))
        else:
            raise AskConfigError(f"Vector store initialization failed: {message}") from exc

    prompt = build_rag_prompt_template()

    def _build_chain(model):
        return (
            {
                "context": retriever | RunnableLambda(_format_context),
                "question": RunnablePassthrough(),
            }
            | prompt
            | model
            | StrOutputParser()
        )

    chain = _build_chain(llm)

    try:
        return _invoke_with_timeout(chain, question)
    except Exception as exc:
        raise AskError(_format_llm_error(exc)) from exc
