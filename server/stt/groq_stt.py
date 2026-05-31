"""STT через Groq Whisper API (хмарне розпізнавання мови)."""

import base64
import httpx

from server.config import settings


async def transcribe_groq(audio_data: bytes, sample_rate: int = 16000) -> str:
    """Надсилає аудіо в Groq Whisper API і повертає розпізнаний текст."""
    url = "https://api.groq.com/openai/v1/audio/transcriptions"
    headers = {"Authorization": f"Bearer {settings.groq_api_key}"}

    # Конвертуємо raw PCM у WAV в пам'яті
    import wave
    import io
    wav_buffer = io.BytesIO()
    with wave.open(wav_buffer, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(sample_rate)
        wf.writeframes(audio_data)
    wav_bytes = wav_buffer.getvalue()
    wav_buffer.close()

    files = {"file": ("audio.wav", wav_bytes, "audio/wav")}
    data = {"model": settings.groq_stt_model, "language": "uk", "response_format": "json"}

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(url, headers=headers, files=files, data=data)
        resp.raise_for_status()
        result = resp.json()
        return result.get("text", "")
