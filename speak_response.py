"""Скрипт: викликає /api/speak з текстом з аргумента або stdin."""
import sys, httpx, json, base64

text = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else sys.stdin.read().strip()
if not text:
    print("Usage: python speak_response.py <text>")
    print("   or: echo 'text' | python speak_response.py")
    sys.exit(1)

resp = httpx.post("http://localhost:8888/api/speak", json={
    "text": text, "voice": "F1", "lang": "uk"
}, timeout=60)
if resp.status_code == 200:
    data = resp.json()
    audio = base64.b64decode(data["audio"])
    sys.stdout.buffer.write(audio)
    print(f"\n✅ Озвучено: {len(audio)} bytes", file=sys.stderr)
else:
    print(f"❌ Помилка: {resp.status_code} {resp.text}", file=sys.stderr)
    sys.exit(1)
