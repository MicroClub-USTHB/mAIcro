from .openai_provider import OpenAIProvider

llm = OpenAIProvider()
print(llm.generate("Explain vector databases in simple terms."))