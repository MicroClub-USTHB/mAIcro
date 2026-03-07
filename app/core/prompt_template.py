from langchain_core.prompts import PromptTemplate

from app.core.config import settings

_BASE_TEMPLATE = """\
You are the official AI assistant for {org_name}.

About {org_name}:
{org_description}

Your core rules:
{core_rules}

Always ground your answers in verified information about {org_name}. \
If you do not know something, say so clearly rather than speculating.
"""

_RAG_TEMPLATE = """\
{system_prompt}

You are answering a member question using retrieved context snippets.

Response quality requirements:
1. Be concise, factual, and professional.
2. Use only facts supported by the provided context.
3. If context is insufficient, say exactly: "I don't have this information yet."
4. Do not invent dates, links, names, or procedures.

Output format:
- Start with a direct answer in 1-3 sentences.
- If relevant, add a short "Details:" paragraph.
- If context is missing or ambiguous, add "Missing info:" with what is needed.

Context snippets:
{context}

User question:
{question}

Final answer:
"""


def build_system_prompt() -> str:
    if settings.CORE_RULES:
        rules_block = "\n".join(
            f"  {i + 1}. {rule}" for i, rule in enumerate(settings.CORE_RULES)
        )
    else:
        rules_block = "Be helpful, accurate, and professional."

    return _BASE_TEMPLATE.format(
        org_name=settings.ORG_NAME,
        org_description=settings.ORG_DESCRIPTION or "An organization using mAIcro.",
        core_rules=rules_block,
    )


def build_rag_prompt_template() -> PromptTemplate:
    """Return the reusable prompt template for retrieval-augmented answering."""
    return PromptTemplate(
        template=_RAG_TEMPLATE,
        input_variables=["context", "question"],
        partial_variables={"system_prompt": build_system_prompt()},
    )


def preview_prompt() -> None:
    prompt = build_system_prompt()
    separator = "-" * 60
    print(f"\n{separator}")
    print("  SYSTEM PROMPT PREVIEW")
    print(separator)
    print(prompt)
    print(separator + "\n")


if __name__ == "__main__":
    preview_prompt()
