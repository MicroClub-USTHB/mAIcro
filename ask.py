import sys
from app.core.vector_store import get_vector_store
from app.core.llm_provider import get_llm
from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
from app.core.config import settings


class AskError(Exception):
    """Raised when asking the LLM fails with a user-actionable error."""


def _format_llm_error(exc: Exception) -> str:
    """Convert provider errors into short messages suitable for CLI users."""
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
            "Verify your provider key in .env (GOOGLE_API_KEY or ANTHROPIC_API_KEY)."
        )

    return f"Request failed: {message}"

def ask_question(question: str):
    llm = get_llm()
    vector_store = get_vector_store()
    
    # Simple RAG chain
    prompt_template = """
    You are mAIcro, an AI assistant for {org_name}.
    Answer the user question based ONLY on the provided context.
    If the context doesn't contain the answer, say "I don't have this information yet."
    
    Context:
    {context}
    
    Question: {question}
    
    Answer:"""
    
    PROMPT = PromptTemplate(
        template=prompt_template,
        input_variables=["context", "question"],
        partial_variables={"org_name": settings.ORG_NAME}
    )
    
    # Runnable solution
    retriever = vector_store.as_retriever(search_kwargs={"k": 3})
    
    chain = (
        {"context": retriever, "question": RunnablePassthrough()}
        | PROMPT
        | llm
        | StrOutputParser()
    )
    
    try:
        return chain.invoke(question)
    except Exception as exc:
        raise AskError(_format_llm_error(exc)) from exc

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

    if provider not in {"google", "anthropic"}:
        print("Error: LLM_PROVIDER must be either 'google' or 'anthropic'.")
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
