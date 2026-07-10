import time
from pathlib import Path
from loguru import logger
from fastapi import BackgroundTasks
from sqlalchemy.orm import Session as DBSession

from app.models.session import Session
from app.models.presentation_job import PresentationJob
from app.db.database import SessionLocal
from app.core.constants import JobStatus, UploadType
from app.repositories.presentation_job_repository import presentation_job_repository
from app.modules.induction.validation.validator import validate_session_assets
from app.modules.induction.parser.ppt_parser import parse_presentation
from app.modules.induction.employees.excel_parser import parse_employees_excel
from app.modules.induction.employees.validator import validate_employee_rows
from app.modules.induction.employees.profiler import profile_employees
from app.modules.induction.employees.audience_builder import build_audience_summary
from app.modules.induction.context.meeting_context import build_meeting_context
from app.modules.induction.llm.preparation_orchestrator import generate_induction_package_scripts
from app.modules.induction.package.package_builder import build_and_save_package
from app.modules.induction.parser.media_extractor import storage_service

class InductionService:
    def __init__(self):
        # Dictionary to store durations of the last executed pipeline steps (v1.3 timing inspection)
        self.last_run_timings = {}

    def prepare_session(self, db: DBSession, session_id: str, background_tasks: BackgroundTasks) -> PresentationJob:
        """
        Creates or retrieves a PresentationJob and enqueues the preparation pipeline in background.
        """
        job = presentation_job_repository.get_by_session(db, session_id)
        if not job:
            job = presentation_job_repository.create(db, session_id=session_id)
        else:
            presentation_job_repository.update(db, job, status=JobStatus.PENDING, progress=0.0, error_message=None)

        background_tasks.add_task(self._run_pipeline, session_id, job.id)
        return job

    def prepare_induction(self, db: DBSession, session_id: str, background_tasks: BackgroundTasks) -> PresentationJob:
        return self.prepare_session(db, session_id, background_tasks)

    def get_job_status(self, db: DBSession, session_id: str) -> dict:
        job = presentation_job_repository.get_by_session(db, session_id)
        if not job:
            return {"status": "not_started", "progress": 0.0}
        return {"status": job.status, "progress": job.progress, "error_message": job.error_message}

    async def _run_pipeline(self, session_id: str, job_id: str):
        logger.info(f"Starting preparation pipeline for session {session_id} (Job ID: {job_id})")
        db = SessionLocal()
        self.last_run_timings = {}
        start_total = time.perf_counter()
        try:
            # Fetch fresh objects in thread
            session = db.query(Session).filter(Session.id == session_id).first()
            job = presentation_job_repository.get(db, job_id)
            if not session or not job:
                logger.error("Session or Job not found in background task.")
                return

            # Step 1: Validation Engine (10%)
            logger.info("Pipeline Step 1: Running asset validations...")
            t0 = time.perf_counter()
            ppt_path, excel_path = validate_session_assets(db, session_id)
            self.last_run_timings["Validation"] = time.perf_counter() - t0
            presentation_job_repository.update(db, job, progress=0.1)

            # Step 2: PPT Intelligence (30%)
            logger.info("Pipeline Step 2: Extracting PowerPoint contents...")
            t0 = time.perf_counter()
            session_dir = Path(storage_service.get_session_upload_dir(session_id, UploadType.PRESENTATION)).parent
            slide_knowledge = parse_presentation(ppt_path, session_dir)
            self.last_run_timings["PPT Parser"] = time.perf_counter() - t0
            presentation_job_repository.update(db, job, progress=0.3)

            # Step 3: Employee Intelligence (50%)
            logger.info("Pipeline Step 3: Reading and profiling employee attendee list...")
            t0 = time.perf_counter()
            raw_rows = parse_employees_excel(excel_path)
            validate_employee_rows(raw_rows)
            employee_profiles = profile_employees(raw_rows)
            audience_summary = build_audience_summary(employee_profiles)
            self.last_run_timings["Employee Intelligence"] = time.perf_counter() - t0
            presentation_job_repository.update(db, job, progress=0.5)

            # Step 4: Meeting Context & LLM preparation script generation (90%)
            logger.info("Pipeline Step 4: Building meeting context and triggering AI generators...")
            t0 = time.perf_counter()
            meeting_context = build_meeting_context(session)

            session_metadata = {
                "name": session.name,
                "scheduled_at": session.scheduled_at.isoformat() if session.scheduled_at else None
            }

            # Generate intros, welcome flows, slide narrations, question scripts
            scripts = await generate_induction_package_scripts(
                session_metadata=session_metadata,
                meeting_context=meeting_context,
                employee_profiles=employee_profiles,
                audience_summary=audience_summary,
                slide_knowledge=slide_knowledge
            )
            self.last_run_timings["LLM Generation"] = time.perf_counter() - t0
            presentation_job_repository.update(db, job, progress=0.9)

            # Step 5: Packaging (100%)
            logger.info("Pipeline Step 5: Compiling and saving induction_package.json...")
            t0 = time.perf_counter()
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
            self.last_run_timings["Package Builder"] = time.perf_counter() - t0

            self.last_run_timings["Total"] = time.perf_counter() - start_total

            # Mark complete
            presentation_job_repository.update(db, job, status=JobStatus.COMPLETED, progress=1.0)
            logger.info(f"Pipeline completed successfully for session {session_id}.")

        except Exception as e:
            logger.exception(f"Pipeline crashed for session {session_id}.")
            self.last_run_timings["Total"] = time.perf_counter() - start_total
            error_db = SessionLocal()
            try:
                job = presentation_job_repository.get(error_db, job_id)
                if job:
                    presentation_job_repository.update(
                        error_db, job, status=JobStatus.FAILED, error_message=str(e)
                    )
            finally:
                error_db.close()
            raise e
        finally:
            db.close()

induction_service = InductionService()
