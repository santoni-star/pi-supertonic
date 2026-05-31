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
import httpx
import base64

TTS_SERVER = "http://localhost:8888"


def play_audio_sync(mp3_bytes: bytes):
    """Відтворити MP3 на Windows без відкриття додаткових вікон.

    Конвертуємо у WAV через ffmpeg (pipe) і граємо через winsound.
    """
    import winsound
    import wave
    import io

    # ffmpeg: mp3 (stdin) → wav (stdout)
    proc = subprocess.run(
        ["ffmpeg", "-i", "pipe:0", "-f", "wav", "pipe:1", "-y", "-loglevel", "quiet"],
        input=mp3_bytes,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0 or len(proc.stdout) < 100:
        # fallback: зберегти у файл і відкрити
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            f.write(mp3_bytes)
            tmp = f.name
        os.startfile(tmp)
        return

    # winsound грає WAV з пам'яті
    try:
        winsound.PlaySound(proc.stdout, winsound.SND_MEMORY)
    except Exception:
        # fallback: записати у тимчасовий файл
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(proc.stdout)
            tmp = f.name
        try:
            winsound.PlaySound(tmp, winsound.SND_FILENAME)
        finally:
            os.unlink(tmp)


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

        if fmt == "wav":
            import winsound
            try:
                winsound.PlaySound(audio_bytes, winsound.SND_MEMORY)
            except Exception:
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                    f.write(audio_bytes)
                    tmp = f.name
                try:
                    winsound.PlaySound(tmp, winsound.SND_FILENAME)
                finally:
                    os.unlink(tmp)
        else:
            play_audio_sync(audio_bytes)

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
