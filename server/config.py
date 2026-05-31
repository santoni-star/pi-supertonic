"""Pi-Supertonic — конфігурація."""

import json
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings

CONFIG_FILE = Path(__file__).resolve().parent.parent / "config.json"


class Settings(BaseSettings):
    # TTS (Supertonic server)
    tts_api_url: str = "http://127.0.0.1:8765"
    tts_voice: str = "F1"
    tts_lang: str = "uk"
    tts_speed: float = 1.05
    tts_steps: int = 8
    tts_format: Literal["wav", "mp3"] = "mp3"

    # Server
    host: str = "0.0.0.0"
    port: int = 8888

    # STT
    groq_api_key: str = ""
    groq_stt_model: str = "whisper-large-v3"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    def save(self):
        data = {
            "tts_api_url": self.tts_api_url,
            "tts_voice": self.tts_voice,
            "tts_lang": self.tts_lang,
            "tts_speed": self.tts_speed,
            "tts_steps": self.tts_steps,
            "tts_format": self.tts_format,
            "host": self.host,
            "port": self.port,
            "groq_api_key": self.groq_api_key,
            "groq_stt_model": self.groq_stt_model,
        }
        CONFIG_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    def load_json(self):
        if not CONFIG_FILE.exists():
            return
        try:
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            for key, value in data.items():
                if hasattr(self, key) and value is not None:
                    field_type = self.model_fields.get(key)
                    if field_type:
                        if field_type.annotation is float:
                            value = float(value)
                        elif field_type.annotation is int:
                            value = int(value)
                    setattr(self, key, value)
            print(f"[config] loaded from {CONFIG_FILE}")
        except (json.JSONDecodeError, Exception) as e:
            print(f"[config] error: {e}")


settings = Settings()
settings.load_json()
