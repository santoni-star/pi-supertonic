"""Pi-Supertonic — конфігурація."""

from pydantic_settings import BaseSettings
from typing import Literal


class Settings(BaseSettings):
    # LLM
    llm_provider: Literal["groq", "openai", "ollama"] = "groq"
    groq_api_key: str = ""
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1:8b"

    # STT
    groq_stt_model: str = "whisper-large-v3"

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

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
