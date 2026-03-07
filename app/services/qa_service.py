"""Question-answering service built on top of retrieval-augmented generation."""

from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnableLambda, RunnablePassthrough

from app.core.llm_provider import get_llm
from app.core.prompt_template import build_rag_prompt_template
from app.core.vector_store import get_vector_store


class AskError(Exception):
    """Raised when asking the LLM fails with a user-actionable error."""


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
            "Verify your provider key in .env (GOOGLE_API_KEY, ANTHROPIC_API_KEY, or GROQ_API_KEY)."
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
    llm = get_llm()
    vector_store = get_vector_store()

    prompt = build_rag_prompt_template()
    retriever = vector_store.as_retriever(search_kwargs={"k": 3})

    chain = (
        {
            "context": retriever | RunnableLambda(_format_context),
            "question": RunnablePassthrough(),
        }
        | prompt
        | llm
        | StrOutputParser()
    )

    try:
        return chain.invoke(question)
    except Exception as exc:
        raise AskError(_format_llm_error(exc)) from exc
