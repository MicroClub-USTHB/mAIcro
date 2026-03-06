from app.core.config import settings




def build_prompt(prompt_name: str, **kwargs) -> str:
    """
    Build a full prompt string based on the prompt name and arguments.
    """


    system_prompt = (
        f"You are an AI assistant for {settings.ORG_NAME}. "
        f"Organization description: {settings.ORG_DESCRIPTION}."
    )


    if prompt_name == "chat":
        user_prompt = kwargs.get("prompt", "")
        return f"{system_prompt}\n\nUser: {user_prompt}"


    elif prompt_name == "summarize":
        text = kwargs.get("text", "")
        return f"{system_prompt}\n\nSummarize the following text:\n{text}"


    elif prompt_name == "explain":
        topic = kwargs.get("topic", "")
        return f"{system_prompt}\n\nExplain the following concept clearly:\n{topic}"


    else:
        raise ValueError(f"Unknown prompt: {prompt_name}")