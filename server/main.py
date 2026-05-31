"""Pi-Supertonic — головний сервер.

Режими:
- chat: по черзі (текст → LLM → TTS)
- realtime: VAD 3с + перебивання (аудіо → STT → LLM → TTS → аудіо)
"""

import asyncio
import json
import time
import base64
import uuid
from contextlib import asynccontextmanager
from typing import Literal

import httpx
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from server.config import settings
from server.llm.factory import get_llm_provider
from server.stt.groq_stt import transcribe_groq
from server.tts.supertonic_client import synthesize, get_voices, get_languages

# ---------- стан ----------

llm = get_llm_provider()
conversation_history: list[dict] = []
system_prompt = (
    "Ти — Pi-Supertonic, голосовий асистент. Відповідай природно, "
    "розмовною українською мовою. Відповіді мають бути короткими "
    "(2-4 речення), бо це голосовий діалог. Не використовуй markdown, "
    "зірочок, списків — тільки чистий текст."
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup
    yield
    # shutdown

app = FastAPI(title="Pi-Supertonic", version="0.1.0", lifespan=lifespan)

# ---------- REST API ----------

@app.get("/api/config")
async def get_config():
    """Поточна конфігурація (без секретів)."""
    return {
        "llm_provider": settings.llm_provider,
        "tts_voice": settings.tts_voice,
        "tts_lang": settings.tts_lang,
        "tts_speed": settings.tts_speed,
        "tts_steps": settings.tts_steps,
        "tts_format": settings.tts_format,
        "mode": "chat",
    }


@app.post("/api/config")
async def update_config(data: dict):
    """Оновлює налаштування (в цій сесії)."""
    for key, value in data.items():
        if hasattr(settings, key):
            setattr(settings, key, value)
    return {"ok": True}


@app.get("/api/voices")
async def voices():
    voices_list = await get_voices()
    return voices_list


@app.post("/api/stt/groq")
async def stt_groq_endpoint(data: dict):
    """STT через Groq Whisper (з raw аудіо)."""
    import base64
    audio_b64 = data.get("audio", "")
    sample_rate = data.get("sample_rate", 16000)
    if not audio_b64:
        raise HTTPException(400, "audio is required")
    audio_bytes = base64.b64decode(audio_b64)
    text = await transcribe_groq(audio_bytes, sample_rate)
    return {"text": text}


@app.get("/api/languages")
async def languages():
    return await get_languages()


@app.post("/api/chat")
async def chat_endpoint(data: dict):
    """Режим чату: отримує текст, повертає аудіо (MP3/WAV)."""
    user_text = data.get("text", "").strip()
    if not user_text:
        raise HTTPException(400, "text is required")

    conversation_history.append({"role": "user", "content": user_text})

    # LLM
    response_text = await llm.chat_sync(conversation_history, system_prompt)
    conversation_history.append({"role": "assistant", "content": response_text})

    # TTS
    audio_bytes = await synthesize(
        text=response_text,
        voice=data.get("voice", settings.tts_voice),
        lang=data.get("lang", settings.tts_lang),
        speed=data.get("speed", settings.tts_speed),
        steps=data.get("steps", settings.tts_steps),
        fmt=data.get("format", settings.tts_format),
    )

    return JSONResponse({
        "response_text": response_text,
        "audio": base64.b64encode(audio_bytes).decode(),
        "format": settings.tts_format,
    })


@app.post("/api/chat/text")
async def chat_text_endpoint(data: dict):
    """Тільки текст (без TTS) — для відладки."""
    user_text = data.get("text", "").strip()
    if not user_text:
        raise HTTPException(400, "text is required")

    conversation_history.append({"role": "user", "content": user_text})
    response_text = await llm.chat_sync(conversation_history, system_prompt)
    conversation_history.append({"role": "assistant", "content": response_text})
    return {"response_text": response_text}


@app.post("/api/reset")
async def reset_conversation():
    conversation_history.clear()
    return {"ok": True}


# ---------- WebSocket (режим realtime) ----------

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    local_history: list[dict] = []

    try:
        while True:
            raw = await ws.receive_text()
            msg = json.loads(raw)
            event = msg.get("type")

            if event == "ping":
                await ws.send_json({"type": "pong"})

            elif event == "config_update":
                for key, value in msg.get("data", {}).items():
                    if hasattr(settings, key):
                        setattr(settings, key, value)
                await ws.send_json({"type": "config_updated"})

            elif event == "reset":
                local_history.clear()
                await ws.send_json({"type": "reset_ok"})

            elif event == "audio_chunk":
                # Аудіо-фрагмент від браузера (base64)
                audio_b64 = msg.get("audio", "")
                sample_rate = msg.get("sample_rate", 16000)
                audio_bytes = base64.b64decode(audio_b64)

                # Перевірка: чи це кінець фрази (тиша)?
                is_end = msg.get("end_of_phrase", False)

                if is_end:
                    # Транскрибуємо аудіо
                    await ws.send_json({"type": "status", "message": "transcribing..."})
                    try:
                        user_text = await transcribe_groq(audio_bytes, sample_rate)
                    except Exception as e:
                        await ws.send_json({"type": "error", "message": f"STT error: {e}"})
                        continue

                    if not user_text.strip():
                        await ws.send_json({"type": "status", "message": "no speech detected"})
                        continue

                    await ws.send_json({"type": "transcription", "text": user_text})
                    local_history.append({"role": "user", "content": user_text})

                    # LLM
                    await ws.send_json({"type": "status", "message": "thinking..."})
                    full_response = ""
                    async for chunk in llm.chat(local_history, system_prompt, stream=True):
                        full_response += chunk
                        await ws.send_json({"type": "llm_chunk", "text": chunk})

                    local_history.append({"role": "assistant", "content": full_response})

                    # TTS
                    await ws.send_json({"type": "status", "message": "synthesizing..."})
                    try:
                        audio_bytes_tts = await synthesize(
                            text=full_response,
                            fmt=settings.tts_format,
                        )
                        await ws.send_json({
                            "type": "audio",
                            "audio": base64.b64encode(audio_bytes_tts).decode(),
                            "format": settings.tts_format,
                            "text": full_response,
                        })
                    except Exception as e:
                        await ws.send_json({"type": "error", "message": f"TTS error: {e}"})
                else:
                    # Проміжний chunk — просто підтверджуємо
                    await ws.send_json({"type": "audio_chunk_ack"})

            elif event == "interrupt":
                # Користувач перебив — зупиняємо TTS
                await ws.send_json({"type": "interrupt_ack"})

    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await ws.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass


# ---------- статика ----------

app.mount("/", StaticFiles(directory="client", html=True), name="client")


# ---------- точка входу ----------

def run():
    import uvicorn
    uvicorn.run("server.main:app", host=settings.host, port=settings.port, reload=True)
