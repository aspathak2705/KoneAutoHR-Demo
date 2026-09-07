import hashlib
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, Tuple
from fastapi import UploadFile

class StorageProvider(ABC):
    @abstractmethod
    def calculate_hash(self, file_path: Path) -> str:
        pass

    @abstractmethod
    async def calculate_upload_hash(self, file: UploadFile) -> str:
        pass

    @abstractmethod
    def exists(self, storage_key: str) -> bool:
        pass

    @abstractmethod
    def get_path(self, storage_key: str) -> Path:
        pass

    @abstractmethod
    def delete(self, storage_key: str) -> bool:
        pass

    @abstractmethod
    async def save_file(self, file: UploadFile, relative_dir: str, custom_filename: Optional[str] = None) -> Tuple[str, str, int, str]:
        pass
