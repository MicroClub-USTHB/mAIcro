import google.generativeai as genai

from app.core.llm_provider import LLMProvider
from app.core.config import settings
from app.promts.promts import build_system_prompt

class GeminiProvider(LLMProvider):
    def __init__(self):
        genai.configure(api_key=settings.GEMINI_API_KEY)
        self.model = genai.GenerativeModel(settings.LLM_MODEL)


    def generate(self, prompt: str) -> str:
        system_prompt = build_system_prompt()
           
        
        
        full_prompt = f"{system_prompt}\n\nUser: {prompt}"

        response = self.model.generate_content(full_prompt)
        return response.text