import shutil
from pathlib import Path
from fastapi import UploadFile
from app.core.config import settings
from app.core.constants import UploadType
from app.utils.file_utils import sanitize_filename

class StorageService:
    def __init__(self):
        self.base_dir = Path(settings.UPLOAD_DIR)

    def get_session_upload_dir(self, session_id: str, upload_type: UploadType) -> Path:
        subfolder = upload_type.value.lower() if hasattr(upload_type, "value") else str(upload_type).lower()
        target_dir = self.base_dir / f"session_{session_id}" / subfolder
        target_dir.mkdir(parents=True, exist_ok=True)
        return target_dir

    def create_session_directories(self, session_id: str):
        """
        Creates all required folder directories for a session immediately upon creation.
        """
        self.get_session_upload_dir(session_id, UploadType.PRESENTATION)
        self.get_session_upload_dir(session_id, UploadType.EMPLOYEE_LIST)

    async def save_file(self, session_id: str, file: UploadFile, upload_type: UploadType) -> tuple[str, str, int]:
        """
        Saves uploaded file to disk.
        Returns:
            tuple: (filename, absolute_file_path_str, size_bytes)
        """
        target_dir = self.get_session_upload_dir(session_id, upload_type)
        sanitized_filename = sanitize_filename(file.filename)
        target_path = target_dir / sanitized_filename

        # Write to file
        size = 0
        with target_path.open("wb") as buffer:
            while chunk := await file.read(1024 * 1024):
                buffer.write(chunk)
                size += len(chunk)

        return sanitized_filename, str(target_path.resolve()), size

    def delete_session_files(self, session_id: str):
        session_dir = self.base_dir / f"session_{session_id}"
        if session_dir.exists() and session_dir.is_dir():
            shutil.rmtree(session_dir)

storage_service = StorageService()
