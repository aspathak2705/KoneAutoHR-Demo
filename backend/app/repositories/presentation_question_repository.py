from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession
from typing import List, Optional
from app.models.presentation_question import PresentationQuestion

class PresentationQuestionRepository:
    def get(self, db: DBSession, id: str) -> Optional[PresentationQuestion]:
        stmt = select(PresentationQuestion).where(PresentationQuestion.id == id)
        return db.scalars(stmt).first()

    def get_by_presentation(self, db: DBSession, presentation_id: str) -> List[PresentationQuestion]:
        stmt = select(PresentationQuestion).where(PresentationQuestion.presentation_id == presentation_id).order_by(PresentationQuestion.generated_at.desc())
        return list(db.scalars(stmt).all())

    def get_active(self, db: DBSession, presentation_id: str) -> Optional[PresentationQuestion]:
        stmt = select(PresentationQuestion).where(
            PresentationQuestion.presentation_id == presentation_id,
            PresentationQuestion.status == "ACTIVE"
        ).order_by(PresentationQuestion.generated_at.desc())
        return db.scalars(stmt).first()

    def create(self, db: DBSession, presentation_id: str, questions_content: str) -> PresentationQuestion:
        # Mark other questions for this presentation as archived
        db.query(PresentationQuestion).filter(
            PresentationQuestion.presentation_id == presentation_id,
            PresentationQuestion.status == "ACTIVE"
        ).update({"status": "ARCHIVED"})
        db_obj = PresentationQuestion(
            presentation_id=presentation_id,
            questions_content=questions_content,
            status="ACTIVE"
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def update(self, db: DBSession, db_obj: PresentationQuestion, **kwargs) -> PresentationQuestion:
        for key, value in kwargs.items():
            setattr(db_obj, key, value)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def delete(self, db: DBSession, id: str) -> Optional[PresentationQuestion]:
        db_obj = self.get(db, id)
        if db_obj:
            db.delete(db_obj)
            db.commit()
        return db_obj

presentation_question_repository = PresentationQuestionRepository()
