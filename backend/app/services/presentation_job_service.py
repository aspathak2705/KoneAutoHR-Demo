from sqlalchemy.orm import Session as DBSession
from typing import Optional
from app.repositories.presentation_job_repository import presentation_job_repository
from app.models.presentation_job import PresentationJob
from app.core.constants import JobStatus

class PresentationJobService:
    def get_job(self, db: DBSession, job_id: str) -> Optional[PresentationJob]:
        return presentation_job_repository.get(db, job_id)

    def get_job_by_session(self, db: DBSession, session_id: str) -> Optional[PresentationJob]:
        return presentation_job_repository.get_by_session(db, session_id)

    def create_job(self, db: DBSession, session_id: str) -> PresentationJob:
        return presentation_job_repository.create(db, session_id)

    def update_job_status(
        self,
        db: DBSession,
        job_id: str,
        status: JobStatus,
        progress: Optional[float] = None,
        error_message: Optional[str] = None
    ) -> Optional[PresentationJob]:
        job = presentation_job_repository.get(db, job_id)
        if not job:
            return None
        return presentation_job_repository.update(db, job, status, progress, error_message)

presentation_job_service = PresentationJobService()
