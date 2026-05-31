"""Базовий клас для LLM провайдерів."""

from abc import ABC, abstractmethod
from typing import AsyncIterator


class LLMProvider(ABC):
    @abstractmethod
    async def chat(
        self,
        messages: list[dict],
        system_prompt: str | None = None,
        stream: bool = True,
    ) -> AsyncIterator[str]:
        """Надсилає повідомлення в LLM і повертає відповідь потоково (str chunks)."""
        ...

    @abstractmethod
    async def chat_sync(self, messages: list[dict], system_prompt: str | None = None) -> str:
        """Надсилає повідомлення і повертає повний текст відповіді."""
        ...
