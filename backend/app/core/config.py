import os
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
    LLM_PROVIDER: str = "mock"
    LLM_MODEL: str = "nvidia/nemotron-4-340b-instruct"
    LLM_BASE_URL: str = "https://integrate.api.nvidia.com/v1"
    LLM_API_KEY: str = ""

settings = Settings()
