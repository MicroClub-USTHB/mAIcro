# llm_provider.py
# LLM provider abstraction (OpenAI, local, etc.)

# ...implementation placeholder...

from abc import ABC, abstractmethod


class LLMProvider(ABC):
    """
    Base interface for all LLM providers.
    """

    @abstractmethod
    def generate(self, prompt: str) -> str:
        """
        Generate a response from the LLM.
        """
        pass