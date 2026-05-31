"""Клієнт для doc-tts-server (Supertonic TTS)."""

import httpx
from typing import AsyncIterator
from server.config import settings


TTS_API = settings.tts_api_url


async def get_voices() -> list[dict]:
    """Отримує список доступних голосів з TTS сервера."""
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(f"{TTS_API}/api/voices")
        resp.raise_for_status()
        return resp.json()


async def get_languages() -> list[dict]:
    """Отримує список мов."""
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(f"{TTS_API}/api/languages")
        resp.raise_for_status()
        return resp.json()


async def synthesize(
    text: str,
    voice: str = "",
    lang: str = "",
    speed: float = 0,
    steps: int = 0,
    fmt: str = "",
) -> bytes:
    """Відправляє текст на синтез і повертає аудіо (WAV/MP3 bytes)."""
    payload = {
        "task_id": f"pi-{hash(text) & 0xFFFFFFFF}",
        "text": text,
        "voice": voice or settings.tts_voice,
        "lang": lang or settings.tts_lang,
        "speed": speed or settings.tts_speed,
        "steps": steps or settings.tts_steps,
        "format": fmt or settings.tts_format,
    }

    # 1. Ініціюємо синтез
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(f"{TTS_API}/api/synthesize", json=payload)
        resp.raise_for_status()
        task = resp.json()
        task_id = task.get("task_id")

    if not task_id:
        raise RuntimeError("TTS server didn't return task_id")

    # 2. Чекаємо завершення (polling)
    import asyncio
    for _ in range(120):
        await asyncio.sleep(0.5)
        async with httpx.AsyncClient(timeout=10) as client:
            status_resp = await client.get(f"{TTS_API}/api/status/{task_id}")
            status_resp.raise_for_status()
            status_data = status_resp.json()
            if status_data.get("status") == "completed":
                # 3. Завантажуємо аудіо
                dl_resp = await client.get(f"{TTS_API}/api/download/{task_id}")
                dl_resp.raise_for_status()
                return dl_resp.content
            elif status_data.get("status") == "error":
                raise RuntimeError(f"TTS error: {status_data.get('error', 'unknown')}")

    raise TimeoutError("TTS synthesis timed out")
