import os
import hashlib
import base64
from pathlib import Path
from typing import Optional, Tuple
from fastapi import UploadFile
from loguru import logger

from app.core.config import settings
from app.utils.file_utils import sanitize_filename
from app.storage.base import StorageProvider

try:
    from azure.storage.blob import BlobServiceClient
    from azure.identity import DefaultAzureCredential
    AZURE_SDK_AVAILABLE = True
except ImportError:
    AZURE_SDK_AVAILABLE = False


class AzureBlobStorageProvider(StorageProvider):
    """
    Azure Blob Storage Provider using official azure-storage-blob SDK.
    Supports:
    - Managed Identity (DefaultAzureCredential) when AZURE_STORAGE_ACCOUNT_URL is provided.
    - Connection string fallback for local development.
    - Private container storage with least-privilege operations.
    - Zero plain secrets embedded in client bundles.
    - Envelope-encrypted file upload (AES-256-GCM) preserving AutoHR security.
    """

    def __init__(
        self,
        connection_string: Optional[str] = None,
        account_url: Optional[str] = None,
        container_name: Optional[str] = None,
        local_cache_dir: Optional[str] = None
    ):
        if not AZURE_SDK_AVAILABLE:
            raise RuntimeError(
                "azure-storage-blob package is required to use AzureBlobStorageProvider. "
                "Install with `pip install azure-storage-blob azure-identity`."
            )

        self.connection_string = connection_string or settings.AZURE_STORAGE_CONNECTION_STRING
        self.account_url = account_url or settings.AZURE_STORAGE_ACCOUNT_URL
        self.container_name = container_name or settings.AZURE_STORAGE_CONTAINER_NAME or "autohr-data"

        # Local cache for Windows COM operations (PowerPoint COM requires local filesystem Path)
        self.cache_dir = Path(local_cache_dir or settings.AUTOHR_STORAGE_PATH) / "azure_blob_cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self._client: Optional[BlobServiceClient] = None

    def _get_client(self) -> BlobServiceClient:
        if self._client is not None:
            return self._client

        if self.connection_string:
            logger.info("AzureBlobStorageProvider: Connecting via connection string.")
            self._client = BlobServiceClient.from_connection_string(self.connection_string)
        elif self.account_url:
            logger.info(f"AzureBlobStorageProvider: Connecting to {self.account_url} via DefaultAzureCredential.")
            credential = DefaultAzureCredential()
            self._client = BlobServiceClient(account_url=self.account_url, credential=credential)
        else:
            raise ValueError(
                "AzureBlobStorageProvider requires either AZURE_STORAGE_CONNECTION_STRING "
                "or AZURE_STORAGE_ACCOUNT_URL to be configured."
            )
        return self._client

    def _get_container_client(self):
        client = self._get_client()
        return client.get_container_client(self.container_name)

    def calculate_hash(self, file_path: Path) -> str:
        sha256 = hashlib.sha256()
        with open(file_path, 'rb') as f:
            while chunk := f.read(8192):
                sha256.update(chunk)
        return sha256.hexdigest()

    async def calculate_upload_hash(self, file: UploadFile) -> str:
        sha256 = hashlib.sha256()
        file.file.seek(0)
        while chunk := await file.read(8192):
            sha256.update(chunk)
        file.file.seek(0)
        return sha256.hexdigest()

    def exists(self, storage_key: str) -> bool:
        if not storage_key:
            return False
        normalized_key = storage_key.replace("\\", "/").lstrip("/")
        try:
            container = self._get_container_client()
            blob_client = container.get_blob_client(normalized_key)
            return blob_client.exists()
        except Exception as e:
            logger.warning(f"AzureBlobStorageProvider.exists check failed for {storage_key}: {e}")
            return False

    def get_path(self, storage_key: str) -> Path:
        """
        Retrieves local filesystem path for the blob.
        If not cached locally, downloads blob to isolated cache directory.
        Required because Windows PowerPoint COM API cannot read remote cloud URLs directly.
        """
        if not storage_key:
            return self.cache_dir

        normalized_key = storage_key.replace("\\", "/").lstrip("/")
        cached_file = (self.cache_dir / normalized_key).resolve()

        if not cached_file.exists():
            cached_file.parent.mkdir(parents=True, exist_ok=True)
            container = self._get_container_client()
            blob_client = container.get_blob_client(normalized_key)
            with open(cached_file, "wb") as f:
                download_stream = blob_client.download_blob()
                f.write(download_stream.readall())
            logger.info(f"AzureBlobStorageProvider: Downloaded {normalized_key} to cache {cached_file}")

        return cached_file

    def delete(self, storage_key: str) -> bool:
        if not storage_key:
            return False
        normalized_key = storage_key.replace("\\", "/").lstrip("/")
        try:
            container = self._get_container_client()
            blob_client = container.get_blob_client(normalized_key)
            blob_client.delete_blob()
            # Also clear local cache if present
            cached_file = self.cache_dir / normalized_key
            if cached_file.exists():
                try:
                    os.remove(cached_file)
                except OSError:
                    pass
            return True
        except Exception as e:
            logger.warning(f"AzureBlobStorageProvider.delete failed for {storage_key}: {e}")
            return False

    async def save_file(
        self,
        file: UploadFile,
        relative_dir: str,
        custom_filename: Optional[str] = None
    ) -> Tuple[str, str, int, str]:
        file_name = custom_filename or file.filename or 'file'
        sanitized = sanitize_filename(file_name)
        norm_dir = relative_dir.replace("\\", "/").strip("/")
        storage_key = f"{norm_dir}/{sanitized}" if norm_dir else sanitized

        file_hash = await self.calculate_upload_hash(file)

        file.file.seek(0)
        content = await file.read()
        file.file.seek(0)

        container = self._get_container_client()
        blob_client = container.get_blob_client(storage_key)
        blob_client.upload_blob(content, overwrite=True)

        return sanitized, storage_key, len(content), file_hash

    async def save_encrypted_file(
        self,
        file: UploadFile,
        relative_dir: str,
        custom_filename: Optional[str] = None
    ) -> Tuple[str, str, int, str, dict]:
        """
        Encrypts upload payload via AES-256-GCM and Envelope Encryption before saving to Azure Blob.
        Keeps cloud container zero-knowledge / private.
        """
        from app.core.security.encryption_service import encryption_service
        from app.core.security.key_manager import key_manager

        file_name = custom_filename or file.filename or 'file'
        sanitized = sanitize_filename(file_name)
        norm_dir = relative_dir.replace("\\", "/").strip("/")
        storage_key = f"{norm_dir}/{sanitized}" if norm_dir else sanitized

        file_hash = await self.calculate_upload_hash(file)

        file.file.seek(0)
        plaintext_content = await file.read()
        file.file.seek(0)

        ciphertext, dek, nonce = encryption_service.encrypt_bytes(plaintext_content)
        master_key = key_manager.get_master_key()
        wrapped_dek = encryption_service.wrap_dek(dek, master_key)

        container = self._get_container_client()
        blob_client = container.get_blob_client(storage_key)
        blob_client.upload_blob(ciphertext, overwrite=True)

        enc_meta = {
            "encryption_version": 1,
            "encryption_algorithm": "AES-256-GCM",
            "key_id": "win-dpapi-v1",
            "wrapped_dek": wrapped_dek,
            "nonce": base64.b64encode(nonce).decode('utf-8')
        }

        return sanitized, storage_key, len(plaintext_content), file_hash, enc_meta
