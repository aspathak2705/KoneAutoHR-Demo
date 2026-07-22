import os
import shutil
from abc import ABC, abstractmethod
from loguru import logger

class StorageProvider(ABC):
    @abstractmethod
    def read_file(self, uri: str) -> bytes:
        pass

    @abstractmethod
    def write_file(self, uri: str, data: bytes) -> bool:
        pass

    @abstractmethod
    def resolve_local_path(self, uri: str) -> str:
        pass

class LocalStorageProvider(StorageProvider):
    def read_file(self, uri: str) -> bytes:
        if not os.path.exists(uri):
            raise FileNotFoundError(f"Local file not found: {uri}")
        with open(uri, "rb") as f:
            return f.read()

    def write_file(self, uri: str, data: bytes) -> bool:
        try:
            os.makedirs(os.path.dirname(uri), exist_ok=True)
            with open(uri, "wb") as f:
                f.write(data)
            return True
        except Exception as e:
            logger.error(f"LocalStorageProvider | Failed to write: {e}")
            return False

    def resolve_local_path(self, uri: str) -> str:
        return uri
