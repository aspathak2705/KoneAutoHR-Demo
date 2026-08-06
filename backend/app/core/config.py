import os
from typing import Literal, Optional, List
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, model_validator

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # Simplified Core settings - With default fallbacks
    DATABASE_URL: str = Field("sqlite:///./autohr.db", env="DATABASE_URL")
    UPLOAD_PATH: str = Field("./uploads", env="UPLOAD_PATH")
    MAX_UPLOAD_SIZE: int = Field(52428800, env="MAX_UPLOAD_SIZE")
    ALLOWED_ORIGINS: str = Field("http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173", env="ALLOWED_ORIGINS")
    DEBUG: bool = Field(False, env="DEBUG")
    API_BASE_URL: str = Field("http://localhost:8000", env="API_BASE_URL")

    # Static settings with sensible constants
    APP_NAME: str = "AutoHR-Backend"
    APP_VERSION: str = "1.0.0"
    HOST: str = "127.0.0.1"
    PORT: int = 8000

    # V2 Storage & Voice Provider configurations
    AUTOHR_STORAGE_PATH: str = Field("storage", env="AUTOHR_STORAGE_PATH")
    SARVAM_API_KEY: Optional[str] = Field(None, env="SARVAM_API_KEY")
    SARVAM_BASE_URL: str = Field("https://api.sarvam.ai", env="SARVAM_BASE_URL")
    SARVAM_PROJECT_ID: Optional[str] = Field(None, env="SARVAM_PROJECT_ID")
    EDGE_CHANNEL: str = Field("msedge", env="EDGE_CHANNEL")

    AUDIO_OUTPUT_DEVICE: str = Field("CABLE Input", env="AUDIO_OUTPUT_DEVICE")
    AUDIO_MONITOR_DEVICE: str = Field("Realtek Speakers", env="AUDIO_MONITOR_DEVICE")
    ENABLE_LOCAL_MONITOR: bool = Field(False, env="ENABLE_LOCAL_MONITOR")

    @property
    def VOICE_SAMPLE_DIR(self) -> str:
        return os.path.join(self.AUTOHR_STORAGE_PATH, "voice_samples")

    @property
    def GENERATED_AUDIO_DIR(self) -> str:
        return os.path.join(self.AUTOHR_STORAGE_PATH, "generated_audio")

    @property
    def BROWSER_PROFILE_DIR(self) -> str:
        return os.path.join(self.AUTOHR_STORAGE_PATH, "browser_profiles")

    @property
    def REPORTS_DIR_PATH(self) -> str:
        return os.path.join(self.AUTOHR_STORAGE_PATH, "reports")

    @property
    def UPLOAD_DIR_V2(self) -> str:
        return os.path.join(self.AUTOHR_STORAGE_PATH, "uploads")

    # LLM Settings required for session & script generation
    LLM_PROVIDER: Literal["nvidia", "openai", "ollama"] = "openai"
    LLM_MODEL: str = "nvidia/nemotron-3-super-120b-a12b:free"
    LLM_BASE_URL: str = "https://openrouter.ai/api/v1"
    LLM_API_KEY: Optional[str] = None
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "text"

    @model_validator(mode="before")
    @classmethod
    def check_env_fallbacks(cls, data: dict) -> dict:
        # Force .env file variables to take precedence over host environment variables
        env_file = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env")
        if os.path.exists(env_file):
            with open(env_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" in line:
                        k, v = line.split("=", 1)
                        k = k.strip()
                        v = v.strip().strip('"').strip("'")
                        # Override Pydantic input and OS env
                        data[k] = v
                        os.environ[k] = v

        # Fallback to SQLite if DATABASE_URL contains postgresql but connection fails or is misconfigured
        db_url = data.get("DATABASE_URL") or os.environ.get("DATABASE_URL")
        if db_url and "postgresql" in db_url:
            try:
                import psycopg2
            except ImportError:
                data["DATABASE_URL"] = "sqlite:///./autohr.db"
                os.environ["DATABASE_URL"] = "sqlite:///./autohr.db"
        return data

    # Compatibility properties
    @property
    def AUTOHR_DATABASE_URL(self) -> str:
        return self.DATABASE_URL

    @property
    def UPLOAD_DIR(self) -> str:
        return self.UPLOAD_DIR_V2

    @property
    def allowed_origins(self) -> List[str]:
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",") if origin.strip()]

settings = Settings()

def validate_llm_settings():
    if not settings.LLM_API_KEY:
        import logging
        logger = logging.getLogger("app.core.config")
        logger.warning("LLM CONFIGURATION NOTICE: LLM_API_KEY environment variable is not set.")