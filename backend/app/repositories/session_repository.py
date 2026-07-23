from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession
from typing import List, Optional
from app.models.session import Session
from app.schemas.session import SessionCreate, SessionUpdate

class SessionRepository:
    def get(self, db: DBSession, id: str) -> Optional[Session]:
        stmt = select(Session).where(Session.id == id)
        return db.scalars(stmt).first()

    def get_all(self, db: DBSession, skip: int = 0, limit: int = 100) -> List[Session]:
        stmt = select(Session).order_by(Session.created_at.desc()).offset(skip).limit(limit)
        return list(db.scalars(stmt).all())

    def create(self, db: DBSession, obj_in: SessionCreate) -> Session:
        db_obj = Session(
            name=obj_in.name,
            scheduled_at=obj_in.scheduled_at,
            presentation_id=obj_in.presentation_id,
            employee_list_id=obj_in.employee_list_id
        )
        db.add(db_obj)
        db.flush()
        return db_obj

    def update(self, db: DBSession, db_obj: Session, obj_in: SessionUpdate) -> Session:
        update_data = obj_in.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(db_obj, key, value)
        db.add(db_obj)
        db.flush()
        return db_obj

    def delete(self, db: DBSession, id: str) -> Optional[Session]:
        db_obj = self.get(db, id)
        if db_obj:
            db.delete(db_obj)
            db.flush()
        return db_obj

session_repository = SessionRepository()
