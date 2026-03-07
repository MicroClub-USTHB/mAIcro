import google.genai as genai
from app.services.ai.prompt import build_prompt
from app.core.llm_provider import LLMProvider
from app.core.config import settings
from app.services.ai.prompt import build_prompt

class GeminiProvider(LLMProvider):
    def __init__(self):
        self.client = genai.Client(api_key=settings.GEMINI_API_KEY)


    def generate(self, prompt: str) -> str:
        system_prompt = build_prompt("system")
        
        full_prompt = f"{system_prompt}\n\nUser: {prompt}"

        response = self.client.models.generate_content(
            model=settings.LLM_MODEL,
            contents=full_prompt
        )
        return response.text