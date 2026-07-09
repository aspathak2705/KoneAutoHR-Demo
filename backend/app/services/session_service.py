from sqlalchemy.orm import Session as DBSession
from typing import List
from app.repositories.session_repository import session_repository
from app.models.session import Session
from app.schemas.session import SessionCreate, SessionUpdate
from app.services.presentation_job_service import presentation_job_service
from app.services.storage_service import storage_service
from app.core.exceptions import SessionNotFoundException

class SessionService:
    def create_session(self, db: DBSession, session_in: SessionCreate) -> Session:
        session = session_repository.create(db, session_in)
        storage_service.create_session_directories(session.id)
        presentation_job_service.create_job(db, session.id)
        return session

    def get_session(self, db: DBSession, id: str) -> Session:
        session = session_repository.get(db, id)
        if not session:
            raise SessionNotFoundException(id)
        return session

    def get_all_sessions(self, db: DBSession, skip: int = 0, limit: int = 100) -> List[Session]:
        return session_repository.get_all(db, skip, limit)

    def update_session(self, db: DBSession, id: str, session_in: SessionUpdate) -> Session:
        session = self.get_session(db, id)  # Raises if not found
        return session_repository.update(db, session, session_in)

    def delete_session(self, db: DBSession, id: str) -> Session:
        session = self.get_session(db, id)  # Raises if not found

        # Delete associated files
        storage_service.delete_session_files(id)

        # Delete from repository
        return session_repository.delete(db, id)

session_service = SessionService()
