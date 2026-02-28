from app.core.config import settings 

def build_system_prompt() -> str:
        return (
           f"You are an AI assistant for {settings.ORG_NAME}. "
         f"Organization description: {settings.ORG_DESCRIPTION}."
        )

