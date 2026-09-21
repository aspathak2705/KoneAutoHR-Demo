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

    # Core settings
    DATABASE_URL: str = Field("postgresql://autohr_user:autohr_password@127.0.0.1:5432/autohr")
    UPLOAD_PATH: str = Field("./uploads")
    MAX_UPLOAD_SIZE: int = Field(52428800)
    ALLOWED_ORIGINS: str = Field("http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173")
    DEBUG: bool = Field(False)
    API_BASE_URL: str = Field("http://localhost:8000")
    APP_ENV: str = Field("development")

    # Application constants
    APP_NAME: str = "AutoHR-Backend"
    APP_VERSION: str = "1.0.0"
    HOST: str = "127.0.0.1"
    PORT: int = 8000

    # Authentication & Security settings
    AUTH_TOKEN: Optional[str] = Field(None)
    KEY_PROVIDER: str = Field("windows_dpapi")
    STORAGE_PROVIDER: str = Field("local")

    # V2 Storage & Voice Provider configurations
    AUTOHR_STORAGE_PATH: str = Field("storage")
    SARVAM_API_KEY: Optional[str] = Field(None)
    SARVAM_BASE_URL: str = Field("https://api.sarvam.ai")
    SARVAM_PROJECT_ID: Optional[str] = Field(None)
    EDGE_CHANNEL: str = Field("msedge")

    AUDIO_OUTPUT_DEVICE: str = Field("CABLE Input")
    AUDIO_MONITOR_DEVICE: str = Field("Realtek Speakers")
    ENABLE_LOCAL_MONITOR: bool = Field(False)

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

    # LLM Settings
    LLM_PROVIDER: Literal["nvidia", "openai", "ollama"] = "openai"
    LLM_MODEL: str = "nvidia/nemotron-3-super-120b-a12b:free"
    LLM_BASE_URL: str = "https://openrouter.ai/api/v1"
    LLM_API_KEY: Optional[str] = None
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "text"

    @model_validator(mode="before")
    @classmethod
    def check_env_fallbacks(cls, data: dict) -> dict:
        # 1. Parse .env file if it exists, without overriding existing host OS environment variables
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
                        # Always set in data dict and os.environ so local project .env overrides global OS user env variables
                        data[k] = v
                        os.environ[k] = v
        
        # 2. Check AUTH_TOKEN initialization logic:
        # In production mode, AUTH_TOKEN must be set explicitly.
        app_env = (os.environ.get("APP_ENV") or data.get("APP_ENV") or "development").lower()
        auth_token = os.environ.get("AUTH_TOKEN") or data.get("AUTH_TOKEN")
        if not auth_token:
            if app_env == "production":
                raise ValueError("Security Violation: AUTH_TOKEN must be configured in production environment.")
            else:
                # Local development fallback token
                dev_token = "autohr_dev_secret_token_local"
                data["AUTH_TOKEN"] = dev_token
                os.environ["AUTH_TOKEN"] = dev_token

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