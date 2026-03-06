import google as genai

from app.core.llm_provider import LLMProvider
from app.core.config import settings
from app.services.ai.promt import build_prompt


class GeminiProvider(LLMProvider):

    def __init__(self):
        genai.configure(api_key=settings.GEMINI_API_KEY)
        self.model = genai.GenerativeModel(settings.LLM_MODEL)

    def generate(self, prompt: str) -> str:
        full_prompt = build_prompt("chat", prompt=prompt)

        response = self.model.generate_content(full_prompt)

        return response.text