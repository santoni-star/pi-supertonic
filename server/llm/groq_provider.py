"""LLM провайдер — Groq API (швидкий хмарний LLM)."""

import json
from typing import AsyncIterator

import httpx

from server.config import settings
from server.llm.base import LLMProvider


class GroqProvider(LLMProvider):
    def __init__(self):
        self.base_url = "https://api.groq.com/openai/v1"
        self.model = "llama-3.3-70b-versatile"

    @property
    def _api_key(self) -> str:
        return settings.groq_api_key

    async def _post(self, body: dict, stream: bool = True):
        if not self._api_key:
            raise ValueError(
                "GROQ_API_KEY не налаштовано. Додай ключ у налаштуваннях (⚙️) або в .env"
            )
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json={**body, "stream": stream},
            )
            response.raise_for_status()
            if stream:
                return response
            return response.json()

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
        body = {"model": self.model, "messages": full_messages, "temperature": 0.7, "max_tokens": 4096}

        resp = await self._post(body, stream=True)
        async for line in resp.aiter_lines():
            if line.startswith("data: "):
                data = line[6:].strip()
                if data == "[DONE]":
                    break
                try:
                    chunk = json.loads(data)
                    delta = chunk.get("choices", [{}])[0].get("delta", {})
                    content = delta.get("content", "")
                    if content:
                        yield content
                except json.JSONDecodeError:
                    continue

    async def chat_sync(self, messages: list[dict], system_prompt: str | None = None) -> str:
        full_messages = (
            [{"role": "system", "content": system_prompt}, *messages]
            if system_prompt
            else messages
        )
        body = {"model": self.model, "messages": full_messages, "temperature": 0.7, "max_tokens": 4096}
        data = await self._post(body, stream=False)
        return data["choices"][0]["message"]["content"]
