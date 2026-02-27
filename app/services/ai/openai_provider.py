from openai import OpenAI
from app.core.config import settings
from .llm_provider import LLMProvider

class OpenAIProvider(LLMProvider):
    """
    OpenAI implementation of the LLMProvider interface.
    """

    def __init__(self):
        # Initialize OpenAI client with API key
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
        self.model = settings.LLM_MODEL

    def generate(self, prompt: str) -> str:
        """
        Generate a response from OpenAI LLM using the provided prompt.
        Grounded with organization name and description.
        """
        system_prompt = (
            f"You are an AI assistant for {settings.ORG_NAME}. "
            f"Organization description: {settings.ORG_DESCRIPTION}."
        )

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7
        )

        # Return the AI-generated content
        return response.choices[0].message.content