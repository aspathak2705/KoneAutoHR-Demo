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
    AZURE_KEYVAULT_URL: Optional[str] = Field(None)
    APPLICATIONINSIGHTS_CONNECTION_STRING: Optional[str] = Field(None)
    STORAGE_PROVIDER: str = Field("local")
    AZURE_STORAGE_CONNECTION_STRING: Optional[str] = Field(None)
    AZURE_STORAGE_CONTAINER_NAME: str = Field("autohr-data")
    AZURE_STORAGE_ACCOUNT_URL: Optional[str] = Field(None)

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

    @staticmethod
    def _normalize_database_url(raw_url: str) -> str:
        """
        Normalize database URL for SQLAlchemy / psycopg2 compatibility:
        - Handle postgres:// scheme rewrite to postgresql://
        - Enforce sslmode=require for non-local PostgreSQL connections
        - Sanitize and format for drivers
        """
        url = (raw_url or "").strip()
        if not url:
            return url
        if url.startswith("sqlite"):
            return url

        if url.startswith("postgres://"):
            url = "postgresql://" + url[len("postgres://"):]

        from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse
        try:
            parsed = urlparse(url)
            hostname = (parsed.hostname or "").lower().strip("[]")
            is_local = (
                hostname in ("localhost", "127.0.0.1", "::1", "0.0.0.0")
                or hostname.endswith(".localhost")
                or hostname.startswith("127.")
            )

            query_params = dict(parse_qsl(parsed.query, keep_blank_values=True))
            if not is_local and "sslmode" not in query_params:
                query_params["sslmode"] = "require"

            new_query = urlencode(query_params)
            return urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, parsed.fragment))
        except Exception:
            return url

    @model_validator(mode="before")
    @classmethod
    def check_env_fallbacks(cls, data: dict) -> dict:
        # 1. Parse .env file if it exists, without overriding existing host OS environment variables
        backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        env_candidates = [
            os.path.join(backend_dir, ".env"),
            os.path.join(os.path.dirname(backend_dir), ".env")
        ]
        for env_file in env_candidates:
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
                            if v and k not in data:
                                data[k] = v
                                if k not in os.environ:
                                    os.environ[k] = v


        # 2. Database URL precedence:
        # Precedence: data.get("AUTOHR_DATABASE_URL") > data.get("DATABASE_URL") > os.environ("AUTOHR_DATABASE_URL") > os.environ("DATABASE_URL") > KeyVault (if configured) > default
        raw_db_url = (
            data.get("AUTOHR_DATABASE_URL")
            or data.get("DATABASE_URL")
            or os.environ.get("AUTOHR_DATABASE_URL")
            or os.environ.get("DATABASE_URL")
        )

        # If Azure Key Vault is configured and raw_db_url not explicitly provided, attempt KeyVault lookup
        if not raw_db_url and (data.get("AZURE_KEYVAULT_URL") or os.environ.get("AZURE_KEYVAULT_URL")):
            try:
                from app.core.security.key_manager import AzureKeyVaultProvider
                akv = AzureKeyVaultProvider(vault_url=data.get("AZURE_KEYVAULT_URL") or os.environ.get("AZURE_KEYVAULT_URL"))
                client = akv._get_client()
                secret = client.get_secret("DATABASE-URL")
                if secret and secret.value:
                    raw_db_url = secret.value.strip()
            except Exception:
                pass

        if raw_db_url:
            normalized = cls._normalize_database_url(raw_db_url)
            data["DATABASE_URL"] = normalized


        # 3. Check AUTH_TOKEN initialization logic:
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
    def SANITIZED_DATABASE_URL(self) -> str:
        """
        Return target database URL with credentials masked for safe logging and status reporting.
        """
        from urllib.parse import urlparse, urlunparse
        try:
            parsed = urlparse(self.DATABASE_URL)
            if not parsed.hostname:
                return self.DATABASE_URL
            clean_netloc = parsed.hostname
            if parsed.port:
                clean_netloc += f":{parsed.port}"
            if parsed.username:
                clean_netloc = f"{parsed.username}:***@{clean_netloc}"
            return urlunparse((parsed.scheme, clean_netloc, parsed.path, parsed.params, parsed.query, parsed.fragment))
        except Exception:
            return "postgresql://***:***@hidden/database"

    @property
    def DATABASE_TARGET_INFO(self) -> dict:
        """
        Return sanitized database target host, port, database name, and SSL state.
        """
        from urllib.parse import urlparse, parse_qsl
        try:
            parsed = urlparse(self.DATABASE_URL)
            query_params = dict(parse_qsl(parsed.query, keep_blank_values=True))
            return {
                "scheme": parsed.scheme,
                "host": parsed.hostname or "unknown",
                "port": parsed.port or (5432 if "postgres" in parsed.scheme else None),
                "database": parsed.path.lstrip("/") if parsed.path else "unknown",
                "sslmode": query_params.get("sslmode", "none"),
                "is_remote": not (
                    (parsed.hostname or "") in ("localhost", "127.0.0.1", "::1", "0.0.0.0")
                    or (parsed.hostname or "").startswith("127.")
                )
            }
        except Exception:
            return {"scheme": "unknown", "host": "unknown", "database": "unknown", "sslmode": "unknown", "is_remote": False}

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