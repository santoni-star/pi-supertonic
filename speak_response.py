#!/usr/bin/env python3
"""Озвучити текст через Pi-Supertonic TTS.

Використання:
  python speak_response.py "Текст для озвучення"
  echo "Текст" | python speak_response.py
  python speak_response.py < file.txt

Працює автоматично: текст → /api/speak → Supertonic TTS → 🔊
"""

import sys
import httpx
import json
import base64

TTS_SERVER = "http://localhost:8888"

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
        if resp.status_code == 200:
            data = resp.json()
            print(f"🔊 {len(base64.b64decode(data['audio']))} bytes озвучено", file=sys.stderr)
            return True
        else:
            print(f"❌ {resp.status_code}: {resp.text[:200]}", file=sys.stderr)
            return False
    except httpx.ConnectError:
        print(f"❌ Pi-Supertonic сервер не доступний на {TTS_SERVER}", file=sys.stderr)
        return False
    except Exception as e:
        print(f"❌ Помилка: {e}", file=sys.stderr)
        return False


if __name__ == "__main__":
    if len(sys.argv) > 1:
        text = " ".join(sys.argv[1:])
        speak(text)
    elif not sys.stdin.isatty():
        text = sys.stdin.read().strip()
        speak(text)
    else:
        print("📖 Режим очікування: введи текст і натисни Ctrl+D")
        text = sys.stdin.read().strip()
        speak(text)
