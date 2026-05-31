"""Supertonic TTS — локальний синтез мовлення (без окремого сервера).

Використовує supertonic + ONNX Runtime напряму.
Імпортує TTSManager з doc-tts-server (один раз, ліниво).
"""

import sys
import os
import io
import asyncio
import tempfile
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import soundfile as sf

from server.config import settings


# Можливі шляхи до doc-tts-server backend
_BACKEND_SEARCH_PATHS = [
    Path("C:/Users/VI/Desktop/Нова папка (2)/doc-tts-server/backend"),
    Path.home() / "Desktop" / "Нова папка (2)" / "doc-tts-server" / "backend",
]

_tts_manager = None
_executor = ThreadPoolExecutor(max_workers=1)


def _get_tts_manager():
    """Ліниво ініціалізує TTS Manager (один раз)."""
    global _tts_manager
    if _tts_manager is not None:
        return _tts_manager

    # Шукаємо backend
    backend_path = None
    for p in _BACKEND_SEARCH_PATHS:
        if p.exists() and (p / "synthesizer.py").exists():
            backend_path = str(p.resolve())
            break

    if not backend_path:
        raise RuntimeError(
            "❌ doc-tts-server/backend не знайдено.\n"
            "Переконайся що doc-tts-server встановлено поряд:\n"
            "  C:/Users/VI/Desktop/Нова папка (2)/doc-tts-server/"
        )

    if backend_path not in sys.path:
        sys.path.insert(0, backend_path)

    from synthesizer import tts_manager as mgr
    _tts_manager = mgr
    return _tts_manager


def get_voices() -> list[dict]:
    return {"voices": ["M1", "M2", "M3", "M4", "M5", "F1", "F2", "F3", "F4", "F5"]}


def get_languages() -> list[dict]:
    return [
        {"code": "en", "name": "English"},
        {"code": "uk", "name": "Українська"},
        {"code": "ru", "name": "Русский"},
        {"code": "de", "name": "Deutsch"},
        {"code": "fr", "name": "Français"},
        {"code": "es", "name": "Español"},
        {"code": "ja", "name": "日本語"},
        {"code": "ko", "name": "한국어"},
        {"code": "zh", "name": "中文"},
        {"code": "pt", "name": "Português"},
        {"code": "it", "name": "Italiano"},
        {"code": "pl", "name": "Polski"},
        {"code": "nl", "name": "Nederlands"},
        {"code": "tr", "name": "Türkçe"},
    ]


def _chunk_text(text: str, max_chars: int = 300) -> list[str]:
    """Розбиває текст на частини."""
    if len(text) <= max_chars:
        return [text]

    chunks = []
    for sep in ["! ", "? ", ". ", ".\n", "!\n", "?\n"]:
        text = text.replace(sep, sep + "|||")
    sentences = [s.strip() for s in text.split("|||") if s.strip()]
    current = ""
    for sent in sentences:
        if len(current) + len(sent) < max_chars:
            current += sent + " "
        else:
            if current:
                chunks.append(current.strip())
            current = sent + " "
    if current:
        chunks.append(current.strip())
    return chunks or [text]


def _synthesize_sync(
    text: str,
    voice: str,
    lang: str,
    speed: float,
    steps: int,
    fmt: str,
) -> bytes:
    """Синхронний синтез (виконується в thread pool)."""
    mgr = _get_tts_manager()
    chunks = _chunk_text(text)

    wav, duration = mgr.synthesize_chunks(
        chunks=chunks,
        voice_name=voice,
        lang=lang,
        speed=speed,
        steps=steps,
        use_gpu=False,
        gpu_device_id=0,
        progress_callback=None,
        cancel_event=None,
    )

    # WAV bytes
    buf = io.BytesIO()
    sf.write(buf, wav.squeeze(), 44100, format="wav")
    wav_bytes = buf.getvalue()

    if fmt == "wav":
        return wav_bytes

    # MP3 через ffmpeg
    tmp_wav = tempfile.mktemp(suffix=".wav")
    tmp_mp3 = tempfile.mktemp(suffix=".mp3")
    try:
        with open(tmp_wav, "wb") as f:
            f.write(wav_bytes)
        subprocess.run(
            ["ffmpeg", "-y", "-i", tmp_wav,
             "-codec:a", "libmp3lame", "-b:a", "192k",
             "-f", "mp3", tmp_mp3],
            capture_output=True, check=True,
        )
        with open(tmp_mp3, "rb") as f:
            return f.read()
    finally:
        for p in [tmp_wav, tmp_mp3]:
            try:
                if os.path.exists(p):
                    os.unlink(p)
            except Exception:
                pass


async def synthesize(
    text: str,
    voice: str = "",
    lang: str = "",
    speed: float = 0,
    steps: int = 0,
    fmt: str = "",
) -> bytes:
    """Асинхронний синтез (thread pool, не блокує event loop)."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        _executor,
        _synthesize_sync,
        text,
        voice or settings.tts_voice,
        lang or settings.tts_lang,
        speed or settings.tts_speed,
        steps or settings.tts_steps,
        fmt or settings.tts_format,
    )
