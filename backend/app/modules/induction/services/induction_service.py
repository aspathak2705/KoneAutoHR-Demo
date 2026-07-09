import asyncio
from pathlib import Path
from sqlalchemy.orm import Session as DBSession
from loguru import logger
from fastapi import BackgroundTasks

from app.db.database import SessionLocal
from app.models.session import Session
from app.core.exceptions import ValidationException, SessionNotFoundException
from app.core.constants import JobStatus, UploadType
from app.repositories.presentation_job_repository import presentation_job_repository
from app.services.storage_service import storage_service

from app.modules.induction.validation.validator import validate_session_assets
from app.modules.induction.parser.ppt_parser import parse_presentation
from app.modules.induction.employees.excel_parser import parse_employees_excel
from app.modules.induction.employees.validator import validate_employee_rows
from app.modules.induction.employees.profiler import profile_employees
from app.modules.induction.employees.audience_builder import build_audience_summary
from app.modules.induction.context.meeting_context import build_meeting_context
from app.modules.induction.llm.induction_generator import generate_induction_package_scripts
from app.modules.induction.package.package_builder import build_and_save_package

class InductionService:
    def get_job_status(self, db: DBSession, session_id: str) -> dict:
        job = presentation_job_repository.get_by_session(db, session_id)
        if not job:
            raise SessionNotFoundException(session_id)
        return {
            "status": job.status,
            "progress": job.progress,
            "error_message": job.error_message,
            "created_at": job.created_at,
            "updated_at": job.updated_at
        }

    def prepare_induction(self, db: DBSession, session_id: str, background_tasks: BackgroundTasks) -> dict:
        # 1. Ensure Session exists
        session = db.query(Session).filter(Session.id == session_id).first()
        if not session:
            raise SessionNotFoundException(session_id)

        # 2. Get or create PresentationJob
        job = presentation_job_repository.get_by_session(db, session_id)
        if not job:
            job = presentation_job_repository.create(db, session_id)

        if job.status == JobStatus.PROCESSING.value:
            raise ValidationException("AI Induction Package preparation is already in progress.")

        # 3. Update job state to PROCESSING
        presentation_job_repository.update(db, job, status=JobStatus.PROCESSING, progress=0.0, error_message="")

        # 4. Trigger async background task
        background_tasks.add_task(self._run_pipeline, session_id, job.id)

        return {
            "status": job.status,
            "progress": job.progress,
            "message": "Induction preparation started in the background."
        }

    async def _run_pipeline(self, session_id: str, job_id: str):
        logger.info(f"Starting preparation pipeline for session {session_id} (Job ID: {job_id})")
        db = SessionLocal()
        try:
            # Fetch fresh objects in thread
            session = db.query(Session).filter(Session.id == session_id).first()
            job = presentation_job_repository.get(db, job_id)
            if not session or not job:
                logger.error("Session or Job not found in background task.")
                return

            # Step 1: Validation Engine (10%)
            logger.info("Pipeline Step 1: Running asset validations...")
            ppt_path, excel_path = validate_session_assets(db, session_id)
            presentation_job_repository.update(db, job, progress=0.1)

            # Step 2: PPT Intelligence (30%)
            logger.info("Pipeline Step 2: Extracting PowerPoint contents...")
            session_dir = Path(storage_service.get_session_upload_dir(session_id, UploadType.PRESENTATION)).parent
            slide_knowledge = parse_presentation(ppt_path, session_dir)
            presentation_job_repository.update(db, job, progress=0.3)

            # Step 3: Employee Intelligence (50%)
            logger.info("Pipeline Step 3: Reading and profiling employee attendee list...")
            raw_rows = parse_employees_excel(excel_path)
            validate_employee_rows(raw_rows)
            employee_profiles = profile_employees(raw_rows)
            audience_summary = build_audience_summary(employee_profiles)
            presentation_job_repository.update(db, job, progress=0.5)

            # Step 4: Meeting Context & LLM preparation script generation (90%)
            logger.info("Pipeline Step 4: Building meeting context and triggering AI generators...")
            meeting_context = build_meeting_context(session)

            session_metadata = {
                "name": session.name,
                "scheduled_at": session.scheduled_at.isoformat() if session.scheduled_at else None
            }

            # Generate intros, welcome flows, slide narrations, question scripts
            scripts = await generate_induction_package_scripts(
                session_metadata=session_metadata,
                meeting_context=meeting_context,
                audience_summary=audience_summary,
                slide_knowledge=slide_knowledge
            )
            presentation_job_repository.update(db, job, progress=0.9)

            # Step 5: Packaging (100%)
            logger.info("Pipeline Step 5: Compiling and saving induction_package.json...")
            build_and_save_package(
                session_id=session_id,
                session_metadata=session_metadata,
                meeting_context=meeting_context,
                employee_profiles=employee_profiles,
                audience_summary=audience_summary,
                slide_knowledge=slide_knowledge,
                scripts=scripts,
                session_dir=session_dir
            )

            # Mark complete
            presentation_job_repository.update(db, job, status=JobStatus.COMPLETED, progress=1.0)
            logger.info(f"Pipeline completed successfully for session {session_id}.")

        except Exception as e:
            logger.exception(f"Pipeline crashed for session {session_id}.")
            # Save error state
            db = SessionLocal() # Re-open just in case
            try:
                job = presentation_job_repository.get(db, job_id)
                if job:
                    presentation_job_repository.update(
                        db,
                        job,
                        status=JobStatus.FAILED,
                        progress=0.0,
                        error_message=str(e)
                    )
            except Exception as inner_e:
                logger.error(f"Failed to save error status to database: {inner_e}")
        finally:
            db.close()

induction_service = InductionService()
