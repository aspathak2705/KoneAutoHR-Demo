from fastapi import UploadFile
from sqlalchemy.orm import Session as DBSession
from app.repositories.upload_repository import upload_repository
from app.models.upload import Upload
from app.core.constants import UploadType
from app.services.storage_service import storage_service
from app.utils.validators import validate_presentation_file, validate_employee_list_file

class UploadService:
    def validate_file(self, filename: str, upload_type: UploadType):
        if upload_type == UploadType.PRESENTATION:
            validate_presentation_file(filename)
        elif upload_type == UploadType.EMPLOYEE_LIST:
            validate_employee_list_file(filename)

    async def upload_file(
        self,
        db: DBSession,
        session_id: str,
        file: UploadFile,
        upload_type: UploadType
    ) -> Upload:
        # Validate
        self.validate_file(file.filename, upload_type)

        # Save to disk
        filename, file_path, file_size = await storage_service.save_file(session_id, file, upload_type)

        # Save metadata to DB
        return upload_repository.create(
            db=db,
            session_id=session_id,
            filename=filename,
            original_filename=file.filename,
            file_path=file_path,
            file_size=file_size,
            mime_type=file.content_type or "application/octet-stream",
            upload_type=upload_type
        )

upload_service = UploadService()
