import os
from fastapi import UploadFile, HTTPException, status
from sqlalchemy.orm import Session as DBSession
from app.repositories.upload_repository import upload_repository
from app.models.upload import Upload
from app.core.constants import UploadType
from app.services.storage_service import storage_service

class UploadService:
    def validate_file(self, filename: str, upload_type: UploadType):
        ext = os.path.splitext(filename)[1].lower()
        if upload_type == UploadType.PRESENTATION:
            if ext not in [".ppt", ".pptx"]:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid file format for presentation. Only .ppt and .pptx allowed."
                )
        elif upload_type == UploadType.EMPLOYEES:
            if ext not in [".xls", ".xlsx"]:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid file format for employees list. Only .xls and .xlsx allowed."
                )

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
