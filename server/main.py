"""Pi-Supertonic — голосовий місток.

Архітектура:
  Ти говориш → Pi-Supertonic (STT) → текст у чат
  → я (Pi) відповідаю → /api/speak → TTS → 🔊

Я — мозок. Pi-Supertonic — мої вуха і рот.
"""

import json
import base64
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from server.config import settings
from server.stt.groq_stt import transcribe_groq
from server.tts.supertonic_client import synthesize, get_voices as _get_voices, get_languages as _get_languages


# Черга повідомлень — я (Pi) пишу сюди відповіді, веб-інтерфейс показує
message_queue: list[dict] = []
next_msg_id: int = 0


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(title="Pi-Supertonic", version="0.3.0", lifespan=lifespan)

# ---------- REST API ----------

@app.get("/api/config")
async def get_config():
    return {
        "tts_voice": settings.tts_voice,
        "tts_lang": settings.tts_lang,
        "tts_speed": settings.tts_speed,
        "tts_steps": settings.tts_steps,
        "tts_format": settings.tts_format,
        "groq_api_key": bool(settings.groq_api_key),
    }


@app.post("/api/config")
async def update_config(data: dict):
    for key, value in data.items():
        if hasattr(settings, key):
            setattr(settings, key, value)
    settings.save()
    return {"ok": True}


@app.get("/api/voices")
async def voices():
    return _get_voices()


@app.get("/api/languages")
async def languages():
    return _get_languages()


@app.post("/api/stt/groq")
async def stt_groq_endpoint(data: dict):
    """Розпізнати аудіо через Groq Whisper."""
    audio_b64 = data.get("audio", "")
    sr = data.get("sample_rate", 16000)
    if not audio_b64:
        raise HTTPException(400, "audio is required")
    text = await transcribe_groq(base64.b64decode(audio_b64), sr)
    return {"text": text}


@app.post("/api/speak")
async def speak_endpoint(data: dict):
    """Озвучити текст через TTS. Цей endpoint викликаю я (Pi)."""
    text = data.get("text", "").strip()
    if not text:
        raise HTTPException(400, "text is required")

    audio_bytes = await synthesize(
        text=text,
        voice=data.get("voice", settings.tts_voice),
        lang=data.get("lang", settings.tts_lang),
        speed=data.get("speed", settings.tts_speed),
        steps=data.get("steps", settings.tts_steps),
        fmt=data.get("format", settings.tts_format),
    )
    return JSONResponse({
        "audio": base64.b64encode(audio_bytes).decode(),
        "format": settings.tts_format,
        "text": text,
    })


@app.get("/api/next-transcript")
async def next_transcript():
    """Повертає останню транскрипцію (якщо є нове повідомлення).

    Я (Pi) можу викликати цей endpoint щоб отримати що сказав користувач.
    """
    # transcript_queue зберігається в пам'яті, наповнюється з WebSocket
    if transcript_queue:
        return {"text": transcript_queue.pop(0)}
    return {"text": None}


transcript_queue: list[str] = []


# ---------- Чат: повідомлення від Pi ----------

@app.post("/api/message")
async def post_message(data: dict):
    """Я (Pi) викликаю цей ендпоінт, щоб моя відповідь з'явилась у веб-чаті."""
    global next_msg_id
    msg = {
        "id": next_msg_id,
        "role": "assistant",
        "text": data.get("text", "").strip(),
    }
    next_msg_id += 1
    if msg["text"]:
        message_queue.append(msg)
        # тримаємо тільки останні 50
        while len(message_queue) > 50:
            message_queue.pop(0)
    return {"ok": True, "id": msg["id"]}


@app.get("/api/messages")
async def get_messages(since: int = -1):
    """Веб-інтерфейс отримує нові повідомлення (polling).
    since — останній отриманий ID."""
    new_msgs = [m for m in message_queue if m["id"] > since]
    return {"messages": new_msgs}


# ---------- WebSocket (режим realtime) ----------

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    """WebSocket для realtime режиму.

    Браузер шле аудіо → сервер транскрибує → повертає текст.
    Текст також потрапляє в transcript_queue, звідки я (Pi) його забираю.
    """
    await ws.accept()

    try:
        while True:
            raw = await ws.receive_text()
            msg = json.loads(raw)
            event = msg.get("type")

            if event == "ping":
                await ws.send_json({"type": "pong"})

            elif event == "audio_chunk":
                audio_b64 = msg.get("audio", "")
                sr = msg.get("sample_rate", 16000)
                audio_bytes = base64.b64decode(audio_b64)
                is_end = msg.get("end_of_phrase", False)

                if is_end:
                    await ws.send_json({"type": "status", "message": "transcribing..."})
                    try:
                        user_text = await transcribe_groq(audio_bytes, sr)
                    except ValueError as e:
                        await ws.send_json({"type": "error", "message": str(e)})
                        continue
                    except Exception as e:
                        await ws.send_json({"type": "error", "message": f"STT error: {e}"})
                        continue

                    if not user_text.strip():
                        await ws.send_json({"type": "status", "message": "no speech detected"})
                        continue

                    # Повертаємо в браузер
                    await ws.send_json({
                        "type": "transcription",
                        "text": user_text,
                        "in_chat": True,
                    })

                    # Кладемо в чергу — я (Pi) підберу через /api/next-transcript
                    transcript_queue.append(user_text)

                    await ws.send_json({
                        "type": "status",
                        "message": "Текст передано Pi. Чекаю відповідь...",
                    })
                else:
                    await ws.send_json({"type": "audio_chunk_ack"})

            elif event == "interrupt":
                await ws.send_json({
                    "type": "interrupt_ack",
                    "message": "Чекаю...",
                })

    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await ws.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass


# ---------- Статика ----------

app.mount("/", StaticFiles(directory="client", html=True), name="client")


def run():
    import uvicorn
    uvicorn.run("server.main:app", host=settings.host, port=settings.port, reload=True)
