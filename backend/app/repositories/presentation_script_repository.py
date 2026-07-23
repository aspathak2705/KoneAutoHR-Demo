from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession
from typing import List, Optional
from app.models.presentation_script import PresentationScript

class PresentationScriptRepository:
    def get(self, db: DBSession, id: str) -> Optional[PresentationScript]:
        stmt = select(PresentationScript).where(PresentationScript.id == id)
        return db.scalars(stmt).first()

    def get_by_presentation(self, db: DBSession, presentation_id: str) -> List[PresentationScript]:
        stmt = select(PresentationScript).where(PresentationScript.presentation_id == presentation_id).order_by(PresentationScript.generated_at.desc())
        return list(db.scalars(stmt).all())

    def get_active(self, db: DBSession, presentation_id: str) -> Optional[PresentationScript]:
        stmt = select(PresentationScript).where(
            PresentationScript.presentation_id == presentation_id,
            PresentationScript.status == "ACTIVE"
        ).order_by(PresentationScript.generated_at.desc())
        return db.scalars(stmt).first()

    def create(self, db: DBSession, presentation_id: str, script_content: str, llm_model: str) -> PresentationScript:
        # Mark other scripts for this presentation as archived
        db.query(PresentationScript).filter(
            PresentationScript.presentation_id == presentation_id,
            PresentationScript.status == "ACTIVE"
        ).update({"status": "ARCHIVED"})
        db_obj = PresentationScript(
            presentation_id=presentation_id,
            script_content=script_content,
            llm_model=llm_model,
            status="ACTIVE"
        )
        db.add(db_obj)
        db.flush()
        return db_obj

    def update(self, db: DBSession, db_obj: PresentationScript, **kwargs) -> PresentationScript:
        for key, value in kwargs.items():
            setattr(db_obj, key, value)
        db.add(db_obj)
        db.flush()
        return db_obj

    def delete(self, db: DBSession, id: str) -> Optional[PresentationScript]:
        db_obj = self.get(db, id)
        if db_obj:
            db.delete(db_obj)
            db.flush()
        return db_obj

presentation_script_repository = PresentationScriptRepository()
