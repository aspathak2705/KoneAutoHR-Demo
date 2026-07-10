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
    LLM_PROVIDER: Literal["nvidia", "openai", "ollama"] = "openai"
    LLM_MODEL: str = "nvidia/nemotron-3-super-120b-a12b:free"
    LLM_BASE_URL: str = "https://openrouter.ai/api/v1"
    LLM_API_KEY: Optional[str] = None

settings = Settings()

def validate_llm_settings():
    """
    Validates that the required LLM environment configuration is loaded
    and pings the configured endpoint to verify connectivity.
    Raises ValueError on failure.
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

    # Problem 5 (v1.3) - Ping endpoint to verify credentials and connection
    try:
        headers = {"Authorization": f"Bearer {settings.LLM_API_KEY}"}
        payload = {
            "model": settings.LLM_MODEL,
            "messages": [{"role": "user", "content": "ping"}],
            "max_tokens": 1
        }
        url = f"{settings.LLM_BASE_URL.rstrip('/')}/chat/completions"
        with httpx.Client(timeout=8.0) as client:
            response = client.post(url, headers=headers, json=payload)
            if response.status_code == 401:
                raise ValueError("CRITICAL: LLM connection test failed with status 401 (Unauthorized). Check API Key.")
            elif response.status_code >= 400:
                raise ValueError(f"CRITICAL: LLM connection test failed with status {response.status_code}. Details: {response.text}")
    except httpx.RequestError as e:
        raise ValueError(f"CRITICAL: Failed to connect to LLM endpoint at {settings.LLM_BASE_URL}. Connection Error: {str(e)}")
