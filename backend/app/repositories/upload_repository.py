from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession
from typing import List, Optional
from app.models.upload import Upload
from app.core.constants import UploadType

class UploadRepository:
    def get(self, db: DBSession, id: str) -> Optional[Upload]:
        stmt = select(Upload).where(Upload.id == id)
        return db.scalars(stmt).first()

    def get_by_session(self, db: DBSession, session_id: str) -> List[Upload]:
        stmt = select(Upload).where(Upload.session_id == session_id)
        return list(db.scalars(stmt).all())

    def create(
        self,
        db: DBSession,
        session_id: str,
        filename: str,
        original_filename: str,
        file_path: str,
        file_size: int,
        mime_type: str,
        upload_type: UploadType
    ) -> Upload:
        db_obj = Upload(
            session_id=session_id,
            filename=filename,
            original_filename=original_filename,
            file_path=file_path,
            file_size=file_size,
            mime_type=mime_type,
            upload_type=upload_type.value if hasattr(upload_type, "value") else upload_type
        )
        db.add(db_obj)
        db.flush()
        return db_obj

    def delete(self, db: DBSession, id: str) -> Optional[Upload]:
        db_obj = self.get(db, id)
        if db_obj:
            db.delete(db_obj)
            db.flush()
        return db_obj

upload_repository = UploadRepository()
