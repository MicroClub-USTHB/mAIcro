from app.services.ai.gemini_provider import GeminiProvider

llm = GeminiProvider()
print(llm.generate("Explain vector databases in simple terms."))