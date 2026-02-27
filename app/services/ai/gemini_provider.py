import google.generativeai as genai

from app.core.llm_provider import LLMProvider
from app.core.config import settings
# Hypothetical Gemini SDK import


class GeminiProvider(LLMProvider):
    def __init__(self):
        genai.configure(api_key=settings.GEMINI_API_KEY)
        self.model = genai.GenerativeModel(settings.LLM_MODEL)


    def generate(self, prompt: str) -> str:
        system_prompt = (
            f"You are an AI assistant for {settings.ORG_NAME}. "
            f"Organization description: {settings.ORG_DESCRIPTION}."
        )
        
        full_prompt = f"{system_prompt}\n\nUser: {prompt}"

        response = self.model.generate_content(full_prompt)
        return response.text