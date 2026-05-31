# Pi-Supertonic 🎙️🔊

**Голосовий асистент на базі Supertonic TTS** — твій Pi тепер має голос.

Локальний сервер, який об'єднує розпізнавання мови (STT), велику мовну модель (LLM) і синтез мовлення (TTS) в один голосовий інтерфейс.

## Архітектура

```
Браузер (клієнт)
  │
  ├─ Google STT (Web Speech API, без ключа) — для Chrome
  ├─ або Groq Whisper (хмарний STT)
  │
  ▼
Pi-Supertonic Server (FastAPI)
  │
  ├─ LLM: Groq / OpenAI / Ollama (обирається)
  │
  ▼
doc-tts-server (Supertonic TTS, localhost:8765)
  │
  ▼
Аудіо → колонки
```

## Режими роботи

### 💬 Чат
Почерговий діалог. Можна писати текст або натиснути 🎤 для голосового вводу (Google STT в Chrome або Groq Whisper).

### 🎤 Реальний час
Безперервний діалог:
- Говориш — асистент слухає
- **3 секунди тиші** — асистент відповідає
- **Перебиваєш** — асистент замовкає, слухає уточнення і відповідає з контекстом

## Встановлення

```bash
# 1. Клонувати
git clone https://github.com/santoni-star/pi-supertonic.git
cd pi-supertonic

# 2. Встановити залежності
pip install -r requirements.txt

# 3. Налаштувати (опціонально)
cp .env.example .env
# Відредагувати .env — додати API ключі

# 4. Переконатись, що doc-tts-server працює на localhost:8765

# 5. Запустити
python run.py
```

Відкрити http://127.0.0.1:8888

## Налаштування

| Параметр | Значення за замовчуванням | Опис |
|---|---|---|
| `LLM_PROVIDER` | `groq` | `groq`, `openai`, `ollama` |
| `GROQ_API_KEY` | — | API ключ для Groq (LLM + STT) |
| `OPENAI_API_KEY` | — | API ключ для OpenAI |
| `OLLAMA_MODEL` | `llama3.1:8b` | Модель в локальному Ollama |
| `TTS_VOICE` | `F1` | Голос Supertonic (F1-F5, M1-M5) |
| `TTS_LANG` | `uk` | Мова синтезу |
| `TTS_API_URL` | `http://127.0.0.1:8765` | Адреса doc-tts-server |

## Вимоги

- Python 3.10+
- [doc-tts-server](https://github.com/santoni-star/doc-tts-server) (Supertonic TTS)
- Опціонально: Ollama (для локального LLM), Groq API ключ (для хмарного LLM/STT)

## Ліцензія

MIT
