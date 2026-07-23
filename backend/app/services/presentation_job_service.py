from sqlalchemy.orm import Session as DBSession
from typing import Optional, List
from app.repositories.presentation_job_repository import presentation_job_repository
from app.models.presentation_job import PresentationJob
from app.core.constants import JobStatus
from app.db.unit_of_work import UnitOfWork

class PresentationJobService:
    def get_job(self, db: DBSession, job_id: str) -> Optional[PresentationJob]:
        return presentation_job_repository.get(db, job_id)

    def get_job_by_session(self, db: DBSession, session_id: str, job_type: str = "SCRIPT") -> Optional[PresentationJob]:
        return presentation_job_repository.get_by_session(db, session_id, job_type)

    def get_all_jobs_by_session(self, db: DBSession, session_id: str) -> List[PresentationJob]:
        return presentation_job_repository.get_all_by_session(db, session_id)

    def create_job(self, db: DBSession, session_id: str, job_type: str = "SCRIPT") -> PresentationJob:
        with UnitOfWork(db):
            res = presentation_job_repository.create(db, session_id, job_type)
        return res

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
        with UnitOfWork(db):
            res = presentation_job_repository.update(db, job, status, progress, error_message)
        return res

presentation_job_service = PresentationJobService()
