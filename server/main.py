"""Pi-Supertonic — голосовий місток між тобою і Supertonic TTS.

Режими:
- chat: по черзі (кнопка 🎤 → STT → текст, я відповідаю → /api/speak)
- realtime: VAD 3с + перебивання (аудіо → STT → текст → /api/speak)
"""

import json
import base64
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from server.config import settings
from server.stt.groq_stt import transcribe_groq
from server.tts.supertonic_client import synthesize, get_voices, get_languages


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield

app = FastAPI(title="Pi-Supertonic", version="0.2.0", lifespan=lifespan)

# ---------- REST API ----------

@app.get("/api/config")
async def get_config():
    """Поточна конфігурація."""
    return {
        "tts_voice": settings.tts_voice,
        "tts_lang": settings.tts_lang,
        "tts_speed": settings.tts_speed,
        "tts_steps": settings.tts_steps,
        "tts_format": settings.tts_format,
        "mode": "chat",
    }


@app.post("/api/config")
async def update_config(data: dict):
    """Оновлює налаштування TTS."""
    for key, value in data.items():
        if hasattr(settings, key):
            setattr(settings, key, value)
    settings.save()
    return {"ok": True}


@app.get("/api/voices")
async def voices():
    return await get_voices()


@app.get("/api/languages")
async def languages():
    return await get_languages()


@app.post("/api/stt/groq")
async def stt_groq_endpoint(data: dict):
    """STT через Groq Whisper."""
    audio_b64 = data.get("audio", "")
    sample_rate = data.get("sample_rate", 16000)
    if not audio_b64:
        raise HTTPException(400, "audio is required")
    audio_bytes = base64.b64decode(audio_b64)
    text = await transcribe_groq(audio_bytes, sample_rate)
    return {"text": text}


@app.post("/api/speak")
async def speak_endpoint(data: dict):
    """Отримує текст, синтезує через Supertonic, повертає аудіо.

    Цей endpoint я (Pi) викликаю, щоб озвучити свою відповідь.
    """
    text = data.get("text", "").strip()
    if not text:
        raise HTTPException(400, "text is required")

    try:
        audio_bytes = await synthesize(
            text=text,
            voice=data.get("voice", settings.tts_voice),
            lang=data.get("lang", settings.tts_lang),
            speed=data.get("speed", settings.tts_speed),
            steps=data.get("steps", settings.tts_steps),
            fmt=data.get("format", settings.tts_format),
        )
    except Exception as e:
        raise HTTPException(502, f"TTS error: {e}")

    return JSONResponse({
        "audio": base64.b64encode(audio_bytes).decode(),
        "format": settings.tts_format,
    })


@app.post("/api/reset")
async def reset_conversation():
    return {"ok": True}


# ---------- WebSocket (режим realtime) ----------

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    """WebSocket для realtime режиму.

    Браузер шле аудіо → сервер транскрибує → повертає текст.
    Я (Pi) відповідаю через /api/speak.
    """
    await ws.accept()

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

            elif event == "audio_chunk":
                audio_b64 = msg.get("audio", "")
                sample_rate = msg.get("sample_rate", 16000)
                audio_bytes = base64.b64decode(audio_b64)
                is_end = msg.get("end_of_phrase", False)

                if is_end:
                    await ws.send_json({"type": "status", "message": "transcribing..."})
                    try:
                        user_text = await transcribe_groq(audio_bytes, sample_rate)
                    except Exception as e:
                        await ws.send_json({"type": "error", "message": f"STT error: {e}"})
                        continue

                    if not user_text.strip():
                        await ws.send_json({"type": "status", "message": "no speech detected"})
                        continue

                    # Повертаємо транскрипцію — я (Pi) побачу її і відповім
                    await ws.send_json({
                        "type": "transcription",
                        "text": user_text,
                        "message": "Питання розпізнано. Pi відповідає...",
                    })

                    # Чекаємо відповіді від Pi через /api/speak
                    # Поки що просто сигналізуємо що текст передано
                    await ws.send_json({"type": "status", "message": "чекаю відповідь Pi..."})
                else:
                    await ws.send_json({"type": "audio_chunk_ack"})

            elif event == "interrupt":
                await ws.send_json({"type": "interrupt_ack",
                                     "message": "Чекаю нове питання..."})

    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await ws.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass


# ---------- статика ----------

app.mount("/", StaticFiles(directory="client", html=True), name="client")


def run():
    import uvicorn
    uvicorn.run("server.main:app", host=settings.host, port=settings.port, reload=True)
