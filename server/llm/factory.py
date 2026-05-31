"""Фабрика LLM провайдерів."""

from server.config import settings
from server.llm.base import LLMProvider
from server.llm.groq_provider import GroqProvider
from server.llm.openai_provider import OpenAIProvider
from server.llm.ollama_provider import OllamaProvider


def get_llm_provider() -> LLMProvider:
    match settings.llm_provider:
        case "groq":
            return GroqProvider()
        case "openai":
            return OpenAIProvider()
        case "ollama":
            return OllamaProvider()
        case _:
            raise ValueError(f"Unknown LLM provider: {settings.llm_provider}")
