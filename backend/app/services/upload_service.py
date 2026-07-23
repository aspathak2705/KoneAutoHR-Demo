from fastapi import UploadFile
from sqlalchemy.orm import Session as DBSession
from app.repositories.upload_repository import upload_repository
from app.models.upload import Upload
from app.core.constants import UploadType
from app.services.storage_service import storage_service
from app.utils.upload_validator import upload_validator
from app.core.exceptions import ValidationException
from app.db.unit_of_work import UnitOfWork

class UploadService:
    async def upload_file(
        self,
        db: DBSession,
        session_id: str,
        file: UploadFile,
        upload_type: UploadType
    ) -> Upload:
        # Validate using hardened UploadValidator
        sanitized_filename = await upload_validator.validate(file, upload_type)

        # Save to disk
        filename, file_path, file_size = await storage_service.save_file(session_id, file, upload_type)

        # Check duplicate file contents via MD5 checksum
        checksum = upload_validator.calculate_checksum(file_path)
        existing = db.query(Upload).filter(
            Upload.session_id == session_id,
            Upload.file_size == file_size
        ).all()
        for record in existing:
            if upload_validator.calculate_checksum(record.file_path) == checksum:
                # Remove file from disk
                import os
                try:
                    os.remove(file_path)
                except Exception:
                    pass
                raise ValidationException("Duplicate file upload detected in this session.")

        # Save metadata to DB using UnitOfWork
        with UnitOfWork(db):
            res = upload_repository.create(
                db=db,
                session_id=session_id,
                filename=filename,
                original_filename=file.filename,
                file_path=file_path,
                file_size=file_size,
                mime_type=file.content_type or "application/octet-stream",
                upload_type=upload_type
            )
        db.refresh(res)
        return res

upload_service = UploadService()
