from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession
from typing import Optional
from app.models.presentation_metadata import PresentationMetadata

class PresentationMetadataRepository:
    def get_by_presentation(self, db: DBSession, presentation_id: str) -> Optional[PresentationMetadata]:
        stmt = select(PresentationMetadata).where(PresentationMetadata.presentation_id == presentation_id)
        return db.scalars(stmt).first()

    def create(self, db: DBSession, presentation_id: str, **kwargs) -> PresentationMetadata:
        db_obj = PresentationMetadata(presentation_id=presentation_id, **kwargs)
        db.add(db_obj)
        db.flush()
        return db_obj

    def update(self, db: DBSession, db_obj: PresentationMetadata, **kwargs) -> PresentationMetadata:
        for key, value in kwargs.items():
            setattr(db_obj, key, value)
        db.add(db_obj)
        db.flush()
        return db_obj

presentation_metadata_repository = PresentationMetadataRepository()
