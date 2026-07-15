import os
import httpx
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
    LLM_PROVIDER: Literal["nvidia", "openai", "ollama"] ="openai"
    LLM_MODEL: str = "nvidia/nemotron-3-super-120b-a12b:free"
    LLM_BASE_URL: str = "https://openrouter.ai/api/v1"
    LLM_API_KEY: Optional[str] = None

    # Microsoft OAuth config
    MICROSOFT_CLIENT_ID: Optional[str] = None
    MICROSOFT_CLIENT_SECRET: Optional[str] = None
    MICROSOFT_TENANT_ID: str = "common"
    MICROSOFT_REDIRECT_URI: str = "http://localhost:8000/api/v1/microsoft/callback"
    MICROSOFT_ACCESS_TOKEN: Optional[str] = None

    from pydantic import model_validator

    @model_validator(mode="after")
    def clean_quotes(self) -> "Settings":
        if self.LLM_API_KEY:
            self.LLM_API_KEY = self.LLM_API_KEY.strip("\"'")
        if self.LLM_MODEL:
            self.LLM_MODEL = self.LLM_MODEL.strip("\"'")
        if self.LLM_BASE_URL:
            self.LLM_BASE_URL = self.LLM_BASE_URL.strip("\"'")
        return self

settings = Settings()

def validate_llm_settings():
    """
    Validates that the required LLM environment configuration is loaded
    and pings the configured endpoint to verify connectivity.
    Raises ValueError on fatal failures.
    """
    if not settings.LLM_API_KEY:
        raise ValueError("CRITICAL CONFIGURATION ERROR: LLM_API_KEY environment variable is not set or empty.")
    if settings.LLM_PROVIDER not in ["nvidia", "openai", "ollama"]:
        raise ValueError(f"CRITICAL CONFIGURATION ERROR: Invalid LLM_PROVIDER '{settings.LLM_PROVIDER}'.")
    if not settings.LLM_BASE_URL:
        raise ValueError("CRITICAL CONFIGURATION ERROR: LLM_BASE_URL environment variable is not set or empty.")
    if not settings.LLM_MODEL:
        raise ValueError("CRITICAL CONFIGURATION ERROR: LLM_MODEL environment variable is not set or empty.")

    # Skip actual HTTP ping if the API key matches E2E test mock identifier
    if settings.LLM_API_KEY == "mock_api_key_for_verification_tests":
        return

    import logging
    logger = logging.getLogger("app.core.config")

    # Ping endpoint to verify credentials and connection
    try:
        headers = {"Authorization": f"Bearer {settings.LLM_API_KEY}"}
        payload = {
            "model": settings.LLM_MODEL,
            "messages": [{"role": "user", "content": "ping"}],
            "max_tokens": 1
        }
        is_openrouter = "openrouter.ai" in settings.LLM_BASE_URL
        is_nvidia = settings.LLM_PROVIDER.lower() == "nvidia" or "nvidia.com" in settings.LLM_BASE_URL
        
        if is_openrouter:
            payload["extra_body"] = {
                "reasoning": {"enabled": True}
            }
        elif is_nvidia:
            payload["extra_body"] = {
                "chat_template_kwargs": {"enable_thinking": True},
                "reasoning_budget": 1024
            }
        url = f"{settings.LLM_BASE_URL.rstrip('/')}/chat/completions"
        with httpx.Client(timeout=8.0) as client:
            response = client.post(url, headers=headers, json=payload)
            if response.status_code == 401:
                raise ValueError("CRITICAL: LLM connection test failed with status 401 (Unauthorized). Check API Key.")
            elif response.status_code == 429:
                logger.warning(f"WARNING: LLM connection test returned status 429 (Rate Limit Exceeded). Server starting, but LLM calls may fail. Details: {response.text}")
            elif response.status_code >= 400:
                logger.warning(f"WARNING: LLM connection test failed with status {response.status_code}. Server starting, but LLM calls may fail. Details: {response.text}")
    except httpx.RequestError as e:
        logger.warning(f"WARNING: Failed to connect to LLM endpoint at {settings.LLM_BASE_URL} during startup check. Connection Error: {str(e)}")
