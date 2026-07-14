from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession
from typing import List, Optional
from app.models.presentation import Presentation

class PresentationRepository:
    def get(self, db: DBSession, id: str) -> Optional[Presentation]:
        stmt = select(Presentation).where(Presentation.id == id)
        return db.scalars(stmt).first()

    def get_all(self, db: DBSession, skip: int = 0, limit: int = 100) -> List[Presentation]:
        stmt = select(Presentation).order_by(Presentation.uploaded_at.desc()).offset(skip).limit(limit)
        return list(db.scalars(stmt).all())

    def create(self, db: DBSession, name: str, original_filename: str, storage_path: str, uploaded_by: Optional[str] = None) -> Presentation:
        db_obj = Presentation(
            name=name,
            original_filename=original_filename,
            storage_path=storage_path,
            uploaded_by=uploaded_by
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def update(self, db: DBSession, db_obj: Presentation, **kwargs) -> Presentation:
        for key, value in kwargs.items():
            setattr(db_obj, key, value)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def delete(self, db: DBSession, id: str) -> Optional[Presentation]:
        db_obj = self.get(db, id)
        if db_obj:
            db.delete(db_obj)
            db.commit()
        return db_obj

presentation_repository = PresentationRepository()
