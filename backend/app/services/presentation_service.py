from sqlalchemy.orm import Session as DBSession
from typing import List, Optional
from fastapi import UploadFile
from app.repositories.presentation_repository import presentation_repository
from app.repositories.presentation_metadata_repository import presentation_metadata_repository
from app.models.presentation import Presentation
from app.services.storage_service import storage_service

class PresentationService:
    def get_all(self, db: DBSession, skip: int = 0, limit: int = 100) -> List[Presentation]:
        return presentation_repository.get_all(db, skip, limit)

    def get(self, db: DBSession, id: str) -> Optional[Presentation]:
        return presentation_repository.get(db, id)

    async def create_presentation(self, db: DBSession, name: str, file: UploadFile) -> Presentation:
        sanitized, storage_path, size = await storage_service.save_presentation_file(file)
        
        # Create presentation record
        pres = presentation_repository.create(
            db,
            name=name,
            original_filename=file.filename,
            storage_path=storage_path
        )
        
        # Create metadata child record (defaults)
        presentation_metadata_repository.create(
            db,
            presentation_id=pres.id,
            slide_count=0,
            generation_status="PENDING"
        )
        
        return pres

    def update(self, db: DBSession, id: str, **kwargs) -> Presentation:
        pres = presentation_repository.get(db, id)
        if not pres:
            raise ValueError(f"Presentation with id {id} not found")
        return presentation_repository.update(db, pres, **kwargs)

    def delete(self, db: DBSession, id: str) -> Optional[Presentation]:
        # Delete from disk
        pres = presentation_repository.get(db, id)
        if pres and pres.storage_path:
            import os
            try:
                os.remove(pres.storage_path)
            except OSError:
                pass
        return presentation_repository.delete(db, id)

presentation_service = PresentationService()
