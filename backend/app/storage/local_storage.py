import os
import shutil
import hashlib
from pathlib import Path
from typing import Optional, Tuple
from fastapi import UploadFile
from app.core.config import settings
from app.utils.file_utils import sanitize_filename
from app.storage.base import StorageProvider

class LocalStorageProvider(StorageProvider):
    def __init__(self, base_dir: Optional[str] = None):
        self.base_dir = Path(base_dir or settings.UPLOAD_DIR).resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)

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

    def get_path(self, storage_key: str) -> Path:
        if not storage_key:
            return self.base_dir
        path = Path(storage_key)
        if path.is_absolute():
            return path
        return (self.base_dir / storage_key).resolve()

    def exists(self, storage_key: str) -> bool:
        if not storage_key:
            return False
        return self.get_path(storage_key).exists()

    def delete(self, storage_key: str) -> bool:
        if not storage_key:
            return False
        path = self.get_path(storage_key)
        if path.exists() and path.is_file():
            try:
                os.remove(path)
                return True
            except OSError:
                return False
        return False

    async def save_file(self, file: UploadFile, relative_dir: str, custom_filename: Optional[str] = None) -> Tuple[str, str, int, str]:
        file_name = custom_filename or file.filename or 'file'
        sanitized = sanitize_filename(file_name)
        target_dir = self.get_path(relative_dir)
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / sanitized

        file_hash = await self.calculate_upload_hash(file)
        
        size = 0
        file.file.seek(0)
        with open(target_path, 'wb') as buffer:
            while chunk := await file.read(1024 * 1024):
                buffer.write(chunk)
                size += len(chunk)
        file.file.seek(0)

        rel_key = str(target_path.relative_to(self.base_dir)).replace('\\', '/')
        return sanitized, rel_key, size, file_hash

local_storage = LocalStorageProvider()
