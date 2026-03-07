
from app.core.config import settings

_BASE_TEMPLATE = """\
You are the official AI assistant for {org_name}.

About {org_name}:
{org_description}

Your Core Rules — you must follow these at all times:
{core_rules}

Always ground your answers in verified information about {org_name}. \
If you don't know something, say so clearly rather than speculating.\
"""


def build_system_prompt() -> str:   
    if settings.CORE_RULES:
        rules_block = "\n".join(
            f"  {i + 1}. {rule}" for i, rule in enumerate(settings.CORE_RULES)
        )
    else:
        rules_block = "Be helpful, accurate, and professional."

    prompt = _BASE_TEMPLATE.format(
        org_name=settings.ORG_NAME,
        org_description=settings.ORG_DESCRIPTION or f"An organization using mAIcro.",
        core_rules=rules_block,
    )

    return prompt


def preview_prompt() -> None:
    prompt = build_system_prompt()
    separator = "─" * 60
    print(f"\n{separator}")
    print("  SYSTEM PROMPT PREVIEW")
    print(separator)
    print(prompt)
    print(separator + "\n")


if __name__ == "__main__":
    preview_prompt()
