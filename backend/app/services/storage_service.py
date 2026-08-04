import shutil
from pathlib import Path
from fastapi import UploadFile
from app.core.config import settings
from app.core.constants import UploadType
from app.utils.file_utils import sanitize_filename

class StorageService:
    def __init__(self):
        # Base folder is uploads/sessions
        self.base_dir = Path(settings.UPLOAD_DIR) / "sessions"
        self.presentations_dir = Path(settings.UPLOAD_DIR) / "presentations"
        self.employee_lists_dir = Path(settings.UPLOAD_DIR) / "employee_lists"
        self.presentations_dir.mkdir(parents=True, exist_ok=True)
        self.employee_lists_dir.mkdir(parents=True, exist_ok=True)

    def get_session_dir(self, session_id: str) -> Path:
        legacy_path = Path("uploads") / "sessions" / session_id
        new_path = self.base_dir / session_id
        if legacy_path.exists() and (legacy_path / "manifest.json").exists() and not (new_path / "manifest.json").exists():
            return legacy_path
        new_path.mkdir(parents=True, exist_ok=True)
        return new_path

    def get_presentation_dir(self, session_id: str) -> Path:
        p = self.get_session_dir(session_id) / "presentation"
        p.mkdir(parents=True, exist_ok=True)
        return p

    def get_slides_dir(self, session_id: str) -> Path:
        p = self.get_session_dir(session_id) / "slides"
        p.mkdir(parents=True, exist_ok=True)
        return p

    def get_videos_dir(self, session_id: str) -> Path:
        p = self.get_session_dir(session_id) / "videos"
        p.mkdir(parents=True, exist_ok=True)
        return p

    def get_images_dir(self, session_id: str) -> Path:
        p = self.get_session_dir(session_id) / "images"
        p.mkdir(parents=True, exist_ok=True)
        return p

    def get_reports_dir(self, session_id: str) -> Path:
        p = Path(settings.REPORTS_DIR_PATH) / session_id
        p.mkdir(parents=True, exist_ok=True)
        return p

    def get_generated_audio_dir(self, session_id: str) -> Path:
        p = Path(settings.GENERATED_AUDIO_DIR) / f"session_{session_id}"
        p.mkdir(parents=True, exist_ok=True)
        return p

    def get_voice_samples_dir(self) -> Path:
        p = Path(settings.VOICE_SAMPLE_DIR)
        p.mkdir(parents=True, exist_ok=True)
        return p

    def get_induction_package_path(self, session_id: str) -> Path:
        return self.get_session_dir(session_id) / "induction_package.json"

    def get_preview_script_path(self, session_id: str) -> Path:
        return self.get_reports_dir(session_id) / "final_induction_script.md"

    def get_session_upload_dir(self, session_id: str, upload_type: UploadType) -> Path:
        subfolder = upload_type.value.lower() if hasattr(upload_type, "value") else str(upload_type).lower()
        if subfolder == "presentation":
            return self.get_presentation_dir(session_id)
        elif subfolder == "employee_list":
            p = self.get_session_dir(session_id) / "employee_list"
            p.mkdir(parents=True, exist_ok=True)
            return p
        else:
            p = self.get_session_dir(session_id) / subfolder
            p.mkdir(parents=True, exist_ok=True)
            return p

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

    async def save_presentation_file(self, file: UploadFile) -> tuple[str, str, int]:
        sanitized = sanitize_filename(file.filename)
        target_path = self.presentations_dir / sanitized
        size = 0
        with target_path.open("wb") as buffer:
            while chunk := await file.read(1024 * 1024):
                buffer.write(chunk)
                size += len(chunk)
        return sanitized, str(target_path.resolve()), size

    async def save_employee_list_file(self, file: UploadFile) -> tuple[str, str, int]:
        sanitized = sanitize_filename(file.filename)
        target_path = self.employee_lists_dir / sanitized
        size = 0
        with target_path.open("wb") as buffer:
            while chunk := await file.read(1024 * 1024):
                buffer.write(chunk)
                size += len(chunk)
        return sanitized, str(target_path.resolve()), size

    def delete_session_files(self, session_id: str):
        session_dir = self.get_session_dir(session_id)
        if session_dir.exists() and session_dir.is_dir():
            shutil.rmtree(session_dir)

storage_service = StorageService()
