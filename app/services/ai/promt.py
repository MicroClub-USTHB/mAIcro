from pathlib import Path
from app.core.config import settings

PROMPTS_DIR = Path(__file__).parents / "prompts"


def build_prompt(prompt_name: str, **kwargs) -> str:
    prompt_path = PROMPTS_DIR / f"{prompt_name}.md"

    if not prompt_path.exists():
        raise ValueError(f"Unknown prompt: {prompt_name}")

    template = prompt_path.read_text()

    return template.format(
        org_name=settings.ORG_NAME,
        org_description=settings.ORG_DESCRIPTION,
        **kwargs
    )