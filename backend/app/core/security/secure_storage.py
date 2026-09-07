import os
import shutil
import base64
import uuid
from pathlib import Path
from contextlib import contextmanager
from typing import Generator, Optional
from loguru import logger

from app.core.config import settings
from app.core.security.encryption_service import encryption_service
from app.core.security.key_manager import key_manager
from app.storage.local_storage import local_storage

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
    Secure Storage Layer providing transparent encrypted asset access.
    Decrypts encrypted assets on-the-fly into controlled temporary context files for runtime processing.
    """
    @contextmanager
    def open_decrypted_file(self, entity_model) -> Generator[Path, None, None]:
        """
        Context manager that decrypts entity storage file and yields temp plaintext Path.
        If entity is legacy unencrypted (encryption_version == 0), returns physical path directly.
        """
        full_path = local_storage.get_path(entity_model.storage_path)
        
        # Legacy unencrypted fallback
        if getattr(entity_model, "encryption_version", 0) == 0:
            yield full_path
            return

        # Decrypt encrypted asset
        with open(full_path, "rb") as f:
            ciphertext = f.read()

        master_key = key_manager.get_master_key()
        dek = encryption_service.unwrap_dek(entity_model.wrapped_dek, master_key)
        nonce = base64.b64decode(entity_model.nonce.encode('utf-8'))
        
        plaintext = encryption_service.decrypt_bytes(ciphertext, dek, nonce)
        
        suffix = Path(entity_model.original_filename).suffix or ".tmp"
        with secure_temp_manager.create_temp_plaintext_file(plaintext, file_suffix=suffix) as temp_path:
            yield temp_path

secure_storage = SecureStorage()
