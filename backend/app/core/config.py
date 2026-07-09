import os
from typing import Literal, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

    APP_NAME: str = "AutoHR-Backend"
    APP_VERSION: str = "1.0.0"
    HOST: str = "127.0.0.1"
    PORT: int = 8000
    AUTOHR_DATABASE_URL: str = "sqlite:///./autohr.db"
    UPLOAD_DIR: str = "./uploads"
    LOG_LEVEL: str = "INFO"

    # LLM config
    LLM_PROVIDER: Literal["mock", "nvidia", "openai", "ollama"] = "mock"
    LLM_MODEL: str = "nvidia/nemotron-3-super-120b-a12b:free"
    LLM_BASE_URL: str = "https://openrouter.ai/api/v1"
    LLM_API_KEY: Optional[str] = None

settings = Settings()
