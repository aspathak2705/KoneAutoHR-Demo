import os
import json
import base64
from pathlib import Path
from typing import Protocol, Optional
from loguru import logger

class KeyProvider(Protocol):
    def get_master_key(self) -> bytes:
        ...
    def get_key_by_id(self, key_id: str) -> bytes:
        ...

class BaseKeyProvider:
    """
    Base key provider with common helper logic for generating master key.
    """
    def __init__(self, key_store_dir: Optional[Path] = None):
        from app.core.config import settings
        self.key_store_dir = key_store_dir or (Path(settings.AUTOHR_STORAGE_PATH) / "keys")
        self.key_store_dir.mkdir(parents=True, exist_ok=True)
        self.key_file = self.key_store_dir / "master.key"
        self.meta_file = self.key_store_dir / "keys_metadata.json"

    def _generate_raw_key(self) -> bytes:
        return os.urandom(32)  # 256-bit AES Master Key


class DevelopmentKeyProvider(BaseKeyProvider):
    """
    Development Key Provider.
    Stores obfuscated local master key for non-production environments.
    """
    def get_master_key(self) -> bytes:
        if not self.key_file.exists():
            raw_key = self._generate_raw_key()
            encoded = base64.b64encode(raw_key).decode('utf-8')
            with open(self.key_file, "w", encoding="utf-8") as f:
                f.write(encoded)
            metadata = {
                "provider": "development",
                "master_key_id": "dev-master-v1",
                "algorithm": "AES-256-GCM",
                "created_at": os.path.getctime(self.key_file)
            }
            with open(self.meta_file, "w", encoding="utf-8") as f:
                json.dump(metadata, f, indent=2)
            logger.info("DevelopmentKeyProvider | Generated new local master key.")
            return raw_key
        
        with open(self.key_file, "r", encoding="utf-8") as f:
            encoded = f.read().strip()
        return base64.b64decode(encoded.encode('utf-8'))

    def get_key_by_id(self, key_id: str) -> bytes:
        return self.get_master_key()


class WindowsCredentialKeyProvider(BaseKeyProvider):
    """
    Windows Machine Key Protection Provider using Windows DPAPI (CryptProtectData / CryptUnprotectData).
    Ensures master key cannot be read if files are copied off the Windows machine.
    """
    def get_master_key(self) -> bytes:
        try:
            import win32crypt
        except ImportError:
            raise RuntimeError("win32crypt module unavailable for Windows DPAPI provider.")

        protected_key_file = self.key_store_dir / "master.dpapi"

        if not protected_key_file.exists():
            raw_key = self._generate_raw_key()
            # Encrypt raw key using Windows DPAPI
            # CryptProtectData(DataIn, ScopeDescription, OptionalEntropy, Reserved, PromptStruct, Flags)
            protected_blob = win32crypt.CryptProtectData(
                raw_key,
                "AutoHR Master Key DPAPI Protection",
                None,
                None,
                None,
                0
            )
            with open(protected_key_file, "wb") as f:
                f.write(protected_blob)
            
            metadata = {
                "provider": "windows_dpapi",
                "master_key_id": "win-dpapi-v1",
                "algorithm": "AES-256-GCM",
                "created_at": os.path.getctime(protected_key_file)
            }
            with open(self.meta_file, "w", encoding="utf-8") as f:
                json.dump(metadata, f, indent=2)
            logger.info("WindowsCredentialKeyProvider | Master key generated and protected via Windows DPAPI.")
            return raw_key

        with open(protected_key_file, "rb") as f:
            protected_blob = f.read()

        try:
            _, decrypted_raw_key = win32crypt.CryptUnprotectData(
                protected_blob,
                None,
                None,
                None,
                0
            )
            return decrypted_raw_key
        except Exception as err:
            logger.critical(f"WindowsCredentialKeyProvider | Failed to decrypt master key via DPAPI: {err}")
            raise RuntimeError(f"Windows DPAPI Decryption Failure: {err}")

    def get_key_by_id(self, key_id: str) -> bytes:
        return self.get_master_key()


class AzureKeyVaultProvider(BaseKeyProvider):
    """
    Azure Key Vault Key Provider.
    Retrieves or generates master encryption keys via Azure Key Vault SecretClient
    using Managed Identity (DefaultAzureCredential).
    """
    def __init__(self, vault_url: Optional[str] = None):
        super().__init__()
        from app.core.config import settings
        self.vault_url = vault_url or settings.AZURE_KEYVAULT_URL
        self.secret_name = "autohr-master-key"
        self._client = None

    def _get_client(self):
        if self._client is not None:
            return self._client
        if not self.vault_url:
            raise ValueError(
                "AzureKeyVaultProvider configuration error: AZURE_KEYVAULT_URL is not configured."
            )
        try:
            from azure.keyvault.secrets import SecretClient
            from azure.identity import DefaultAzureCredential
            credential = DefaultAzureCredential()
            self._client = SecretClient(vault_url=self.vault_url, credential=credential)
            return self._client
        except ImportError:
            raise RuntimeError(
                "azure-keyvault-secrets and azure-identity packages are required for AzureKeyVaultProvider. "
                "Install with `pip install azure-keyvault-secrets azure-identity`."
            )

    def get_master_key(self) -> bytes:
        client = self._get_client()
        try:
            secret = client.get_secret(self.secret_name)
            raw_b64 = secret.value
            return base64.b64decode(raw_b64.encode("utf-8"))
        except Exception as e:
            # Check if secret not found (create/seed it if authorized)
            err_msg = str(e).lower()
            if "not found" in err_msg or "secretnotfound" in err_msg:
                try:
                    logger.info("AzureKeyVaultProvider | Master key secret not found. Generating new 256-bit AES master key in vault...")
                    new_key = self._generate_raw_key()
                    encoded = base64.b64encode(new_key).decode("utf-8")
                    client.set_secret(self.secret_name, encoded)
                    return new_key
                except Exception as create_err:
                    logger.critical(f"AzureKeyVaultProvider | Failed to generate master key in Key Vault: {create_err}")
                    raise
            logger.critical(f"AzureKeyVaultProvider | Failed to retrieve master key from Key Vault: {e}")
            raise

    def get_key_by_id(self, key_id: str) -> bytes:
        client = self._get_client()
        try:
            secret = client.get_secret(key_id)
            return base64.b64decode(secret.value.encode("utf-8"))
        except Exception as e:
            logger.critical(f"AzureKeyVaultProvider | Failed to retrieve key '{key_id}' from Key Vault: {e}")
            raise


class KeyManager:
    """
    Key Manager resolving current configured KeyProvider (windows_dpapi, development, azure_keyvault).
    """
    def __init__(self):
        self._provider: Optional[KeyProvider] = None

    def _initialize_provider(self):
        from app.core.config import settings
        provider_type = getattr(settings, "KEY_PROVIDER", "windows_dpapi").lower()

        if provider_type == "windows_dpapi":
            try:
                self._provider = WindowsCredentialKeyProvider()
                self._provider.get_master_key()
            except Exception as e:
                if getattr(settings, "APP_ENV", "development").lower() == "production":
                    logger.critical(f"KeyManager | Failed to load Windows DPAPI key provider in production: {e}")
                    raise SystemExit("Security Failure: Windows DPAPI provider failed in production mode.")
                logger.warning(f"KeyManager | DPAPI provider fallback to DevelopmentKeyProvider: {e}")
                self._provider = DevelopmentKeyProvider()
        elif provider_type == "development":
            self._provider = DevelopmentKeyProvider()
        elif provider_type == "azure_keyvault":
            self._provider = AzureKeyVaultProvider()
        else:
            raise ValueError(f"Unsupported KEY_PROVIDER: {provider_type}")

    def get_master_key(self) -> bytes:
        if self._provider is None:
            self._initialize_provider()
        return self._provider.get_master_key()

    def get_key_by_id(self, key_id: str) -> bytes:
        if self._provider is None:
            self._initialize_provider()
        return self._provider.get_key_by_id(key_id)

key_manager = KeyManager()
