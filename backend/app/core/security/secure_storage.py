import os
import shutil
import base64
import uuid
from pathlib import Path
from contextlib import contextmanager
from typing import Generator, Optional
from loguru import logger

from app.core.config import settings
from app.storage.local_storage import get_storage_provider


class SecureTempManager:
    """
    Manages temporary decrypted runtime working files in isolated storage/runtime_temp/ directories.
    Ensures plaintext files are deleted immediately after context exit.
    Includes startup cleanup of stale temporary runtime directories.
    """
    def __init__(self):
        self.temp_base = Path(settings.AUTOHR_STORAGE_PATH) / "runtime_temp"
        self.temp_base.mkdir(parents=True, exist_ok=True)

    def cleanup_stale_temp(self):
        if not self.temp_base.exists():
            return
        count = 0
        for item in self.temp_base.glob("*"):
            try:
                if item.is_dir():
                    shutil.rmtree(item)
                elif item.is_file():
                    os.remove(item)
                count += 1
            except Exception as err:
                logger.warning(f"SecureTempManager | Failed to remove stale temp item {item}: {err}")
        if count > 0:
            logger.info(f"SecureTempManager | Cleaned up {count} stale temporary runtime item(s).")

    @contextmanager
    def create_temp_plaintext_file(self, plaintext: bytes, file_suffix: str = ".tmp") -> Generator[Path, None, None]:
        session_dir = self.temp_base / str(uuid.uuid4())
        session_dir.mkdir(parents=True, exist_ok=True)
        temp_file = session_dir / f"temp_work_{uuid.uuid4().hex[:8]}{file_suffix}"
        
        try:
            with open(temp_file, "wb") as f:
                f.write(plaintext)
            yield temp_file
        finally:
            try:
                if temp_file.exists():
                    os.remove(temp_file)
                if session_dir.exists():
                    shutil.rmtree(session_dir)
            except Exception as err:
                logger.error(f"SecureTempManager | Failed to cleanup temp file {temp_file}: {err}")

secure_temp_manager = SecureTempManager()


class SecureStorage:
    """
    Transparent asset access layer.
    Directly returns physical plaintext file path without application-level encryption.
    """
    @contextmanager
    def open_decrypted_file(self, entity_model) -> Generator[Path, None, None]:
        """
        Context manager that yields physical plaintext Path directly.
        All storage is ordinary unencrypted storage.
        """
        provider = get_storage_provider()
        full_path = provider.get_path(entity_model.storage_path)
        
        if not full_path.exists():
            from app.core.exceptions import StorageFileNotFoundException
            raise StorageFileNotFoundException(
                f"Storage file '{entity_model.storage_path}' referenced by {entity_model.__class__.__name__} "
                f"id={getattr(entity_model, 'id', 'unknown')} not found at physical path: {full_path}",
                {"entity_id": getattr(entity_model, "id", None), "storage_path": entity_model.storage_path}
            )

        yield full_path

    def verify_decryptability(self, storage_path: str, wrapped_dek: Optional[str] = None, nonce: Optional[str] = None) -> bool:
        if not storage_path:
            return False
        provider = get_storage_provider()
        full_path = provider.get_path(storage_path)
        return full_path.exists()

secure_storage = SecureStorage()
SecureTempManager.verify_decryptability = staticmethod(secure_storage.verify_decryptability)
