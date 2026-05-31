#!/usr/bin/env python3
"""Озвучити текст через Pi-Supertonic TTS (реально грає на колонках).

Використання:
  python speak_response.py "Текст для озвучення"
  echo "Текст" | python speak_response.py
"""

import sys
import os
import tempfile
import subprocess
import time
import httpx
import base64

TTS_SERVER = "http://localhost:8888"


def play_mp3(mp3_bytes: bytes):
    """Відтворити MP3 на Windows.

    Стратегія:
    1. ffmpeg → WAV у тимчасовий файл
    2. winsound (неблокуючий)
    3. Файл видаляється після невеликої затримки
    """
    # Конвертуємо MP3 → WAV у тимчасовий файл
    tmp_wav = tempfile.mktemp(suffix=".wav")
    try:
        proc = subprocess.run(
            ["ffmpeg", "-i", "pipe:0", "-f", "wav",
             "-acodec", "pcm_s16le", "-ac", "1", "-ar", "24000",
             "-y", "-loglevel", "quiet", tmp_wav],
            input=mp3_bytes,
            capture_output=True,
            check=False,
        )
        if proc.returncode != 0 or not os.path.exists(tmp_wav) or os.path.getsize(tmp_wav) < 1000:
            print(f"❌ ffmpeg не зміг конвертувати", file=sys.stderr)
            # fallback: просто зберегти mp3 і відкрити
            tmp_mp3 = tempfile.mktemp(suffix=".mp3")
            with open(tmp_mp3, "wb") as f:
                f.write(mp3_bytes)
            os.startfile(tmp_mp3)
            return

        import winsound
        # Граємо асинхронно — не блокуємо
        winsound.PlaySound(tmp_wav, winsound.SND_FILENAME | winsound.SND_ASYNC)
        print(f"🔊 {os.path.getsize(tmp_wav)} bytes WAV", file=sys.stderr)

        # Чекаємо трохи (щоб файл не видалився до завершення відтворення)
        # Тривалість приблизно: bytes / (24000 * 2) секунд
        duration_sec = os.path.getsize(tmp_wav) / (24000 * 2)
        time.sleep(min(duration_sec + 0.5, 30))

    finally:
        try:
            if os.path.exists(tmp_wav):
                os.unlink(tmp_wav)
        except Exception:
            pass


def speak(text: str) -> bool:
    text = text.strip()
    if not text:
        return False

    try:
        resp = httpx.post(
            f"{TTS_SERVER}/api/speak",
            json={"text": text, "voice": "F1", "lang": "uk"},
            timeout=120,
        )
        if resp.status_code != 200:
            print(f"❌ {resp.status_code}: {resp.text[:200]}", file=sys.stderr)
            return False

        data = resp.json()
        audio_b64 = data.get("audio")
        if not audio_b64:
            print("❌ Немає аудіо у відповіді", file=sys.stderr)
            return False

        audio_bytes = base64.b64decode(audio_b64)
        fmt = data.get("format", "mp3")

        print(f"🔊 {len(audio_bytes)} bytes ({fmt})", file=sys.stderr)
        play_mp3(audio_bytes)

        # Також публікуємо повідомлення в чат Pi-Supertonic
        try:
            httpx.post(f"{TTS_SERVER}/api/message", json={"text": text}, timeout=5)
        except Exception:
            pass

        return True

    except httpx.ConnectError:
        print(f"❌ Pi-Supertonic сервер не доступний на {TTS_SERVER}", file=sys.stderr)
        return False
    except Exception as e:
        print(f"❌ Помилка: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    if len(sys.argv) > 1:
        speak(" ".join(sys.argv[1:]))
    elif not sys.stdin.isatty():
        speak(sys.stdin.read().strip())
    else:
        print("📖 Введи текст і натисни Ctrl+D:")
        speak(sys.stdin.read().strip())
