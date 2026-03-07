from app.services.ai.gemini_provider import GeminiProvider

llm = GeminiProvider()
print(llm.generate("Explain what ai is in simple terms."))