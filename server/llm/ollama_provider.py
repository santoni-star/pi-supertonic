"""LLM провайдер — Ollama (локальний LLM)."""

from typing import AsyncIterator

import httpx

from server.config import settings
from server.llm.base import LLMProvider


class OllamaProvider(LLMProvider):
    def __init__(self):
        self.base_url = settings.ollama_base_url.rstrip("/")
        self.model = settings.ollama_model

    async def chat(
        self,
        messages: list[dict],
        system_prompt: str | None = None,
        stream: bool = True,
    ) -> AsyncIterator[str]:
        if system_prompt:
            messages = [{"role": "system", "content": system_prompt}] + messages

        body = {"model": self.model, "messages": messages, "stream": True, "options": {"temperature": 0.7}}

        async with httpx.AsyncClient(timeout=120) as client:
            async with client.stream("POST", f"{self.base_url}/api/chat", json=body) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.strip():
                        continue
                    import json
                    try:
                        chunk = json.loads(line)
                        content = chunk.get("message", {}).get("content", "")
                        if content:
                            yield content
                        if chunk.get("done"):
                            break
                    except json.JSONDecodeError:
                        continue

    async def chat_sync(self, messages: list[dict], system_prompt: str | None = None) -> str:
        if system_prompt:
            messages = [{"role": "system", "content": system_prompt}] + messages

        body = {"model": self.model, "messages": messages, "stream": False, "options": {"temperature": 0.7}}

        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(f"{self.base_url}/api/chat", json=body)
            response.raise_for_status()
            data = response.json()
            return data["message"]["content"]
