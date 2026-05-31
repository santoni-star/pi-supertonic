# Pi-Supertonic 🎙️🔊

**Голос для Pi.** Локальний сервер, який дає мені (Pi) голос через Supertonic TTS.

Це не черговий голосовий асистент. **Мозок — я (Pi).** Ти говориш, я чую, я думаю, я відповідаю — і мій голос звучить через твої колонки.

## Архітектура

```
Ти говориш → [Мікрофон]
       ↓ STT (Google / Groq Whisper)
       ↓ текст
  Я (Pi) думаю і відповідаю
       ↓ моя відповідь
       ↓ POST /api/speak
  Pi-Supertonic Server → Supertonic TTS → 🔊 Аудіо
```

Pi-Supertonic — це **голосовий місток**: STT (розпізнати що ти сказав) + TTS (озвучити мою відповідь).

Supertonic TTS вбудований напряму — **не потребує окремого сервера**.

## Режими роботи

### 💬 Чат
Натискаєш 🎤, говориш — текст розпізнається і показується в чаті. Копіюєш його і надсилаєш мені (Pi) в наш діалог. Я відповідаю. Мою відповідь можна озвучити через `!speak <текст>` або натиснувши кнопку.

### 🎤 Реальний час (експериментальний)
Вмикаєш режим — говориш. Через **3 секунди тиші** аудіо автоматично транскрибується і показується в чаті. Я (Pi) бачу текст і відповідаю. **Перебиваєш мене** — я замовкаю і слухаю знову.

### 🗣 Як я кажу
У цьому чаті я відповідаю текстом. Щоб я заговорила голосом:
- Напиши `!speak Привіт, як справи?` у текстове поле Pi-Supertonic
- Або використай `curl` з терміналу:
  ```bash
  curl -X POST http://localhost:8888/api/speak \
    -H "Content-Type: application/json" \
    -d '{"text":"Привіт, це Pi!"}'
  ```
- Або я сама можу викликати `/api/speak` через bash, коли маю що сказати

## Встановлення

```bash
git clone https://github.com/santoni-star/pi-supertonic.git
cd pi-supertonic
pip install -r requirements.txt
cp .env.example .env
# Supertonic TTS вбудований напряму — окремого сервера не потрібно
python run.py
```

Відкрити http://127.0.0.1:8888

## Налаштування

| Параметр | default | Опис |
|---|---|---|
| `TTS_VOICE` | `F1` | Голос Supertonic |
| `TTS_LANG` | `uk` | Мова |
| `TTS_SPEED` | `1.05` | Швидкість |
| `TTS_STEPS` | `8` | Якість |
| `TTS_FORMAT` | `mp3` | Аудіо формат |
| `GROQ_API_KEY` | — | Для Groq Whisper STT |

## API

| Метод | Шлях | Опис |
|---|---|---|
| `POST` | `/api/speak` | Озвучити текст через TTS |
| `POST` | `/api/stt/groq` | Розпізнати аудіо (Groq) |
| `GET` | `/api/voices` | Список голосів |
| `GET` | `/api/config` | Конфігурація |

**`POST /api/speak`** — головний endpoint, який я використовую щоб говорити:
```json
{"text": "Привіт!", "voice": "F1", "lang": "uk"}
```

## Вимоги

- Python 3.10+
- [doc-tts-server](https://github.com/santoni-star/doc-tts-server) (backend поряд з проектом)
- Chrome/Edge (для Google STT) або Groq API ключ

## Ліцензія

MIT
