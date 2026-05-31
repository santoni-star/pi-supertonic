"""LLM провайдер — OpenAI API."""

from typing import AsyncIterator

from openai import AsyncOpenAI

from server.config import settings
from server.llm.base import LLMProvider


class OpenAIProvider(LLMProvider):
    def __init__(self):
        self.model = settings.openai_model

    @property
    def _client(self) -> AsyncOpenAI:
        if not settings.openai_api_key:
            raise ValueError(
                "OPENAI_API_KEY не налаштовано. Додай ключ у налаштуваннях (⚙️) або в .env"
            )
        return AsyncOpenAI(api_key=settings.openai_api_key)

    async def chat(
        self,
        messages: list[dict],
        system_prompt: str | None = None,
        stream: bool = True,
    ) -> AsyncIterator[str]:
        full_messages = (
            [{"role": "system", "content": system_prompt}, *messages]
            if system_prompt
            else messages
        )
        stream_obj = await self._client.chat.completions.create(
            model=self.model,
            messages=full_messages,
            temperature=0.7,
            max_tokens=4096,
            stream=True,
        )
        async for chunk in stream_obj:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    async def chat_sync(self, messages: list[dict], system_prompt: str | None = None) -> str:
        full_messages = (
            [{"role": "system", "content": system_prompt}, *messages]
            if system_prompt
            else messages
        )
        response = await self._client.chat.completions.create(
            model=self.model,
            messages=full_messages,
            temperature=0.7,
            max_tokens=4096,
        )
        return response.choices[0].message.content
