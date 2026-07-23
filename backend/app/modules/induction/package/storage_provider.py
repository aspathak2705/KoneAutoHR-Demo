import os
import shutil
from abc import ABC, abstractmethod
from pathlib import Path
from app.core.config import settings

class StorageProvider(ABC):
    @abstractmethod
    def save_file(self, relative_path: str, content: bytes) -> str:
        """
        Saves file content to relative path.
        Returns:
            str: storage URI/path
        """
        pass

    @abstractmethod
    def delete_file(self, relative_path: str) -> None:
        """
        Deletes file from storage.
        """
        pass

    @abstractmethod
    def file_exists(self, relative_path: str) -> bool:
        """
        Checks if file exists.
        """
        pass

class LocalStorageProvider(StorageProvider):
    def __init__(self):
        self.base_dir = Path(settings.UPLOAD_DIR)

    def save_file(self, relative_path: str, content: bytes) -> str:
        target_path = self.base_dir / relative_path
        target_path.parent.mkdir(parents=True, exist_ok=True)
        with open(target_path, "wb") as f:
            f.write(content)
        return str(target_path.resolve())

    def delete_file(self, relative_path: str) -> None:
        target_path = self.base_dir / relative_path
        if target_path.exists():
            os.remove(target_path)

    def file_exists(self, relative_path: str) -> bool:
        target_path = self.base_dir / relative_path
        return target_path.exists()

# Global default storage provider instance
storage_provider = LocalStorageProvider()
