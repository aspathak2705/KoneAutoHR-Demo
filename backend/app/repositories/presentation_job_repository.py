from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession
from typing import Optional, List
from app.models.presentation_job import PresentationJob
from app.core.constants import JobStatus

class PresentationJobRepository:
    def get(self, db: DBSession, id: str) -> Optional[PresentationJob]:
        stmt = select(PresentationJob).where(PresentationJob.id == id)
        return db.scalars(stmt).first()

    def get_by_session(self, db: DBSession, session_id: str, job_type: str = "SCRIPT") -> Optional[PresentationJob]:
        stmt = select(PresentationJob).where(
            PresentationJob.session_id == session_id,
            PresentationJob.job_type == job_type
        )
        return db.scalars(stmt).first()

    def get_all_by_session(self, db: DBSession, session_id: str) -> List[PresentationJob]:
        stmt = select(PresentationJob).where(PresentationJob.session_id == session_id)
        return list(db.scalars(stmt).all())

    def create(self, db: DBSession, session_id: str, job_type: str = "SCRIPT") -> PresentationJob:
        db_obj = PresentationJob(
            session_id=session_id,
            job_type=job_type,
            status=JobStatus.PENDING.value
        )
        db.add(db_obj)
        db.flush()
        return db_obj

    def update(
        self,
        db: DBSession,
        db_obj: PresentationJob,
        status: Optional[JobStatus] = None,
        progress: Optional[float] = None,
        error_message: Optional[str] = None
    ) -> PresentationJob:
        if status is not None:
            db_obj.status = status.value if hasattr(status, "value") else status
        if progress is not None:
            db_obj.progress = progress
        if error_message is not None:
            db_obj.error_message = error_message
        db.add(db_obj)
        db.flush()
        return db_obj

presentation_job_repository = PresentationJobRepository()
