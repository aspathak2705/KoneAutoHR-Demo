import os
import re
import shutil
from pathlib import Path
from fastapi import UploadFile
from app.core.config import settings
from app.core.constants import UploadType

class StorageService:
    def __init__(self):
        self.base_dir = Path(settings.UPLOAD_DIR)

    def _sanitize_filename(self, filename: str) -> str:
        # Keep alphanumeric, dot, underscore, dash
        name, ext = os.path.splitext(filename)
        sanitized_name = re.sub(r"[^a-zA-Z0-9_\-]", "", name)
        sanitized_ext = re.sub(r"[^a-zA-Z0-9\.]", "", ext)
        if not sanitized_name:
            sanitized_name = "file"
        return f"{sanitized_name}{sanitized_ext}"

    def get_session_upload_dir(self, session_id: str, upload_type: UploadType) -> Path:
        # Map enum or string to subfolder
        subfolder = upload_type.value.lower() if hasattr(upload_type, "value") else str(upload_type).lower()
        target_dir = self.base_dir / f"session_{session_id}" / subfolder
        target_dir.mkdir(parents=True, exist_ok=True)
        return target_dir

    async def save_file(self, session_id: str, file: UploadFile, upload_type: UploadType) -> tuple[str, str, int]:
        """
        Saves uploaded file to disk.
        Returns:
            tuple: (filename, absolute_file_path_str, size_bytes)
        """
        target_dir = self.get_session_upload_dir(session_id, upload_type)
        sanitized_filename = self._sanitize_filename(file.filename)
        target_path = target_dir / sanitized_filename

        # Write to file
        size = 0
        with target_path.open("wb") as buffer:
            # Read in chunks to prevent high memory usage
            while chunk := await file.read(1024 * 1024):
                buffer.write(chunk)
                size += len(chunk)

        return sanitized_filename, str(target_path.resolve()), size

    def delete_session_files(self, session_id: str):
        session_dir = self.base_dir / f"session_{session_id}"
        if session_dir.exists() and session_dir.is_dir():
            shutil.rmtree(session_dir)

storage_service = StorageService()
