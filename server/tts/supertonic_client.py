"""Клієнт для doc-tts-server (Supertonic TTS)."""

import io
import uuid
import httpx
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
    """Відправляє текст на синтез і повертає аудіо (WAV/MP3 bytes).

    1. Завантажує текст як .txt файл (створює таску)
    2. Запускає синтез з параметрами
    3. Чекає завершення
    4. Повертає аудіо
    """
    task_id = f"pi-{uuid.uuid4().hex[:12]}"
    voice = voice or settings.tts_voice
    lang = lang or settings.tts_lang
    speed = speed or settings.tts_speed
    steps = steps or settings.tts_steps
    fmt_param = fmt or settings.tts_format

    async with httpx.AsyncClient(timeout=30) as client:

        # 1. Upload — створюємо таску з текстовий файлом
        files = {
            "file": (f"{task_id}.txt", text.encode("utf-8"), "text/plain"),
        }
        upload_resp = await client.post(f"{TTS_API}/api/upload", files=files)
        upload_resp.raise_for_status()
        upload_data = upload_resp.json()
        task_id = upload_data["task_id"]  # використовуємо ID від сервера

        # 2. Запускаємо синтез
        synth_payload = {
            "task_id": task_id,
            "text": text,
            "voice": voice,
            "lang": lang,
            "speed": speed,
            "steps": steps,
            "format": fmt_param,
        }
        synth_resp = await client.post(f"{TTS_API}/api/synthesize", json=synth_payload)
        synth_resp.raise_for_status()

        # 3. Чекаємо завершення (polling)
        import asyncio
        for _ in range(180):  # 3 хвилини максимум
            await asyncio.sleep(0.5)
            status_resp = await client.get(f"{TTS_API}/api/status/{task_id}")
            status_resp.raise_for_status()
            status_data = status_resp.json()

            if status_data.get("status") == "completed":
                # 4. Завантажуємо аудіо
                dl_resp = await client.get(f"{TTS_API}/api/download/{task_id}")
                dl_resp.raise_for_status()
                return dl_resp.content

            elif status_data.get("status") == "error":
                error_msg = status_data.get("message", "unknown error")
                raise RuntimeError(f"TTS error: {error_msg}")

    raise TimeoutError("TTS synthesis timed out (3 min)")
