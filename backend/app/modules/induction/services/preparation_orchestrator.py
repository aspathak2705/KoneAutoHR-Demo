import time
import json
from pathlib import Path
from loguru import logger
from sqlalchemy.orm import Session as DBSession

from app.db.database import SessionLocal
from app.models.session import Session
from app.core.constants import JobStatus, SessionStatus
from app.repositories.session_repository import session_repository
from app.schemas.session import SessionUpdate
from app.services.presentation_job_service import presentation_job_service
from app.services.storage_service import storage_service
from app.db.unit_of_work import UnitOfWork

# Modular Pipelines (Content Intelligence Layer)
from app.modules.induction.validation.validation_pipeline import validation_pipeline
from app.modules.induction.parser.parsing_pipeline import parsing_pipeline
from app.modules.induction.context.context_builder import context_builder
from app.modules.induction.services.script_pipeline import script_pipeline
from app.modules.induction.speech.speech_pipeline import speech_pipeline
from app.modules.induction.package.asset_pipeline import asset_pipeline
from app.modules.induction.package.verification_pipeline import verification_pipeline
from app.modules.induction.package.package_builder import package_builder

class PreparationOrchestrator:
    """
    PreparationOrchestrator Coordinates Content Intelligence Layer Pipelines:
    Validation -> Parsing -> Context Builder -> Script -> Speech -> Asset -> Verification -> Package Builder.
    """
    def _get_or_create_job(self, db: DBSession, session_id: str, job_type: str):
        job = presentation_job_service.get_job_by_session(db, session_id=session_id, job_type=job_type)
        if not job:
            job = presentation_job_service.create_job(db, session_id=session_id, job_type=job_type)
        return job

    async def run_preparation(self, session_id: str, trigger_job_id: str) -> None:
        """
        Coordinates Validation Pipeline, Parsing Pipeline, Context Builder, and Script Pipeline.
        """
        logger.info(f"PreparationOrchestrator | Starting preparation orchestration (Session: {session_id})")
        db = SessionLocal()
        try:
            session = db.query(Session).filter(Session.id == session_id).first()
            if not session:
                logger.error(f"PreparationOrchestrator | Session {session_id} not found.")
                return

            val_job = self._get_or_create_job(db, session_id, "VALIDATION")
            parse_job = self._get_or_create_job(db, session_id, "PARSING")
            script_job = self._get_or_create_job(db, session_id, "SCRIPT")

            with UnitOfWork(db):
                presentation_job_service.update_job_status(db, val_job.id, status="PENDING", progress=0.0)
                presentation_job_service.update_job_status(db, parse_job.id, status="PENDING", progress=0.0)
                presentation_job_service.update_job_status(db, script_job.id, status="PENDING", progress=0.0)

            

            session_dir = storage_service.get_session_dir(session_id)
            session_dir.mkdir(parents=True, exist_ok=True)

            # 1. Validation Pipeline
            with UnitOfWork(db):
                session_repository.update(db, session, SessionUpdate(status=SessionStatus.VALIDATING.value))
                presentation_job_service.update_job_status(db, val_job.id, status="PROCESSING", progress=0.1)

            val_report = validation_pipeline.execute(
                db, session.presentation_id, session.employee_list_id, session_id, session_dir
            )

            with UnitOfWork(db):
                presentation_job_service.update_job_status(db, val_job.id, status="COMPLETED", progress=1.0)

            logger.info("===== STEP 1 COMPLETED: Validation =====")

            # 2. Parsing Pipeline
            with UnitOfWork(db):
                session_repository.update(db, session, SessionUpdate(status=SessionStatus.PARSING.value))
                presentation_job_service.update_job_status(db, parse_job.id, status="PROCESSING", progress=0.1)

            parsed_data = parsing_pipeline.execute(
                db=db,
                presentation_id=session.presentation_id,
                ppt_path=val_report["details"]["ppt_path"],
                employee_list_id=session.employee_list_id,
                excel_path=val_report["details"]["excel_path"],
                session_id=session_id,
                session_dir=session_dir
            )

            with UnitOfWork(db):
                presentation_job_service.update_job_status(db, parse_job.id, status="COMPLETED", progress=1.0)

            logger.info("===== STEP 2 COMPLETED: Parsing =====")

            # 3. Context Builder
            structured_context = context_builder.build_context(
                db=db,
                session=session,
                slide_knowledge=parsed_data["slides"],
                employee_rows=parsed_data["employees"]
            )

            logger.info("===== STEP 3 COMPLETED: Context Builder =====")

            with open(session_dir / "structured_context.json", "w", encoding="utf-8") as f:
                json.dump(structured_context, f, indent=2)

            with open(session_dir / "validation_report.json", "w", encoding="utf-8") as f:
                json.dump(val_report, f, indent=2)

            # 4. Script Pipeline
            with UnitOfWork(db):
                session_repository.update(db, session, SessionUpdate(status=SessionStatus.GENERATING_SCRIPT.value))
                presentation_job_service.update_job_status(db, script_job.id, status="PROCESSING", progress=0.1)

            logger.info("===== STEP 4 STARTING: Script Pipeline =====")

            await script_pipeline.execute(db, structured_context, session_dir)

            logger.info("===== STEP 4 COMPLETED: Script Pipeline =====")

            with UnitOfWork(db):
                session_repository.update(db, session, SessionUpdate(status=SessionStatus.UPLOADED.value))
                presentation_job_service.update_job_status(db, script_job.id, status="COMPLETED", progress=1.0)

            logger.info("PreparationOrchestrator | Preparation orchestration completed successfully.")

        except Exception as e:
            logger.exception("PreparationOrchestrator | Preparation failed.")
            try:
                db.rollback()
            except Exception as rollback_err:
                logger.error(f"PreparationOrchestrator | Database rollback failed: {rollback_err}")
            try:
                with UnitOfWork(db):
                    session_repository.update(db, session, SessionUpdate(status=SessionStatus.FAILED.value))
                    for j_type in ["VALIDATION", "PARSING", "SCRIPT"]:
                        j = presentation_job_service.get_job_by_session(db, session_id=session_id, job_type=j_type)
                        if j and j.status != "COMPLETED":
                            presentation_job_service.update_job_status(db, j.id, status="FAILED", error_message=str(e))
            except Exception as update_err:
                logger.error(f"PreparationOrchestrator | Failed to update failure status: {update_err}")
            raise e
        finally:
            db.close()

    async def run_script_generation(self, session_id: str, trigger_job_id: str) -> None:
        await self.run_preparation(session_id, trigger_job_id)

    async def run_audio_generation(self, session_id: str, trigger_job_id: str) -> None:
        """
        Coordinates Speech Pipeline and Asset Pipeline from the stored PresentationScript.
        Does NOT re-execute validation, parsing, context compilation, or script synthesis.
        """
        logger.info(f"PreparationOrchestrator | Starting audio generation orchestration (Session: {session_id})")
        db = SessionLocal()
        try:
            session = db.query(Session).filter(Session.id == session_id).first()
            if not session:
                logger.error(f"PreparationOrchestrator | Session {session_id} not found.")
                return

            # FAIL-FAST: Verify SCRIPT job is completed and script exists in database
            from app.repositories.presentation_script_repository import presentation_script_repository
            db_script = presentation_script_repository.get_active(db, session.presentation_id)

            if not db_script:
                raise ValueError("Presentation script has not been generated. Please complete script generation first.")

            script_job = presentation_job_service.get_job_by_session(db, session_id=session_id, job_type="SCRIPT")
            if not script_job:
                script_job = self._get_or_create_job(db, session_id, "SCRIPT")
            if script_job.status != "COMPLETED":
                with UnitOfWork(db):
                    presentation_job_service.update_job_status(db, script_job.id, status="COMPLETED", progress=1.0)

            audio_job = self._get_or_create_job(db, session_id, "AUDIO")

            with UnitOfWork(db):
                presentation_job_service.update_job_status(db, audio_job.id, status="PENDING", progress=0.0)

            session_dir = storage_service.get_session_dir(session_id)
            session_dir.mkdir(parents=True, exist_ok=True)

            # Re-export script file from DB to session directory (optional disk export)
            script_data = db_script.script_content
            if isinstance(script_data, str):
                script_data = json.loads(script_data)
            with open(session_dir / "session_script.json", "w", encoding="utf-8") as f:
                json.dump(script_data, f, indent=2)

            # 5. Speech Pipeline (TTS)
            with UnitOfWork(db):
                session_repository.update(db, session, SessionUpdate(status=SessionStatus.GENERATING_AUDIO.value))
                presentation_job_service.update_job_status(db, audio_job.id, status="PROCESSING", progress=0.1)

            voice = script_data.get("ai_persona", {}).get("tone", "en-US-AriaNeural")
            audio_tracks = await speech_pipeline.execute(
                db=db,
                session_id=session_id,
                script_payload=script_data,
                voice=voice,
                session_dir=session_dir,
                job=audio_job
            )

            with UnitOfWork(db):
                presentation_job_service.update_job_status(db, audio_job.id, status="COMPLETED", progress=1.0)

            # 6. Asset Pipeline (Catalog & Hash)
            with UnitOfWork(db):
                session_repository.update(db, session, SessionUpdate(status=SessionStatus.REGISTERING_ASSETS.value))
                
            audio_manifest = asset_pipeline.execute(
                db=db,
                presentation_id=session.presentation_id,
                session_id=session_id,
                audio_tracks=audio_tracks,
                session_dir=session_dir
            )

            logger.info("PreparationOrchestrator | Audio generation completed successfully.")

        except Exception as e:
            logger.exception("PreparationOrchestrator | Audio generation failed.")
            try:
                db.rollback()
            except Exception as rollback_err:
                logger.error(f"PreparationOrchestrator | Database rollback failed: {rollback_err}")
            try:
                with UnitOfWork(db):
                    session_repository.update(db, session, SessionUpdate(status=SessionStatus.FAILED.value))
                    j = presentation_job_service.get_job_by_session(db, session_id=session_id, job_type="AUDIO")
                    if j and j.status != "COMPLETED":
                        presentation_job_service.update_job_status(db, j.id, status="FAILED", error_message=str(e))
            except Exception as update_err:
                logger.error(f"PreparationOrchestrator | Failed to update failure status: {update_err}")
            raise e
        finally:
            db.close()

    async def run_package_generation(self, session_id: str, trigger_job_id: str = None) -> None:
        """
        Coordinates Verification Pipeline and Package Builder.
        Consumes final generated artifacts strictly without upstream steps.
        """
        logger.info(f"PreparationOrchestrator | Starting package generation orchestration (Session: {session_id})")
        db = SessionLocal()
        try:
            session = db.query(Session).filter(Session.id == session_id).first()
            if not session:
                logger.error(f"PreparationOrchestrator | Session {session_id} not found.")
                return

            session_dir = storage_service.get_session_dir(session_id)

            # Check upstream statuses and self-heal if artifacts exist
            from app.repositories.presentation_script_repository import presentation_script_repository
            db_script = presentation_script_repository.get_active(db, session.presentation_id)
            if not db_script:
                raise ValueError("Presentation script has not been generated. Please complete script generation first.")

            script_job = presentation_job_service.get_job_by_session(db, session_id=session_id, job_type="SCRIPT")
            if not script_job:
                script_job = self._get_or_create_job(db, session_id, "SCRIPT")
            if script_job.status != "COMPLETED":
                with UnitOfWork(db):
                    presentation_job_service.update_job_status(db, script_job.id, status="COMPLETED", progress=1.0)

            audio_manifest_path = session_dir / "audio_manifest.json"
            audio_job = presentation_job_service.get_job_by_session(db, session_id=session_id, job_type="AUDIO")
            if audio_manifest_path.exists():
                if not audio_job:
                    audio_job = self._get_or_create_job(db, session_id, "AUDIO")
                if audio_job.status != "COMPLETED":
                    with UnitOfWork(db):
                        presentation_job_service.update_job_status(db, audio_job.id, status="COMPLETED", progress=1.0)

            if not audio_job or audio_job.status != "COMPLETED":
                raise ValueError("Upstream phases (Script and Audio) must be completed before packaging.")

            pack_job = self._get_or_create_job(db, session_id, "PACKAGE")
            ver_job = self._get_or_create_job(db, session_id, "VERIFICATION")

            with UnitOfWork(db):
                presentation_job_service.update_job_status(db, pack_job.id, status="PENDING", progress=0.0)
                presentation_job_service.update_job_status(db, ver_job.id, status="PENDING", progress=0.0)

            # Load primary and generated artifacts
            from app.repositories.presentation_script_repository import presentation_script_repository
            db_script = presentation_script_repository.get_active(db, session.presentation_id)
            if not db_script:
                raise FileNotFoundError("Active script not found in database.")
            script_data = db_script.script_content
            if isinstance(script_data, str):
                script_data = json.loads(script_data)

            structured_context_path = session_dir / "structured_context.json"
            validation_report_path = session_dir / "validation_report.json"

            if not structured_context_path.exists() or not validation_report_path.exists():
                logger.info("PreparationOrchestrator | Structured context or validation report missing from disk. Re-parsing local files on-the-fly...")
                validation_report = validation_pipeline.execute(
                    db=db,
                    presentation_id=session.presentation_id,
                    employee_list_id=session.employee_list_id,
                    session_id=session_id,
                    session_dir=session_dir
                )
                parsed_data = parsing_pipeline.execute(
                    db=db,
                    presentation_id=session.presentation_id,
                    ppt_path=validation_report["details"]["ppt_path"],
                    employee_list_id=session.employee_list_id,
                    excel_path=validation_report["details"]["excel_path"],
                    session_id=session_id,
                    session_dir=session_dir
                )
                structured_context = context_builder.build_context(
                    db=db,
                    session=session,
                    slide_knowledge=parsed_data["slides"],
                    employee_rows=parsed_data["employees"]
                )
                with open(structured_context_path, "w", encoding="utf-8") as f:
                    json.dump(structured_context, f, indent=2)
                with open(validation_report_path, "w", encoding="utf-8") as f:
                    json.dump(validation_report, f, indent=2)
            else:
                with open(structured_context_path, "r", encoding="utf-8") as f:
                    structured_context = json.load(f)
                with open(validation_report_path, "r", encoding="utf-8") as f:
                    validation_report = json.load(f)

            audio_manifest_path = session_dir / "audio_manifest.json"
            if not audio_manifest_path.exists():
                raise FileNotFoundError("Audio manifest artifact is missing. Please run audio generation first.")
            with open(audio_manifest_path, "r", encoding="utf-8") as f:
                audio_manifest = json.load(f)

            # 7. Verification Pipeline
            with UnitOfWork(db):
                session_repository.update(db, session, SessionUpdate(status=SessionStatus.VERIFYING.value))
                presentation_job_service.update_job_status(db, ver_job.id, status="PROCESSING", progress=0.1)

            ver_report = verification_pipeline.execute(
                session_id=session_id,
                session_dir=session_dir,
                slides_data=structured_context["presentation"]["slides"],
                employee_profiles=structured_context["audience"]["profiles"],
                presenter_profile=structured_context["presenter_profile"],
                script_data=script_data,
                audio_manifest=audio_manifest
            )

            with UnitOfWork(db):
                presentation_job_service.update_job_status(db, ver_job.id, status="COMPLETED", progress=1.0)

            # 8. Package Builder
            with UnitOfWork(db):
                presentation_job_service.update_job_status(db, pack_job.id, status="PROCESSING", progress=0.1)

            package_builder.build_package(
                session_id=session_id,
                session_dir=session_dir,
                structured_context=structured_context,
                script_data=script_data,
                audio_manifest=audio_manifest,
                validation_report=validation_report
            )

            with UnitOfWork(db):
                session_repository.update(db, session, SessionUpdate(status=SessionStatus.READY.value))
                presentation_job_service.update_job_status(db, pack_job.id, status="COMPLETED", progress=1.0)

            logger.info("PreparationOrchestrator | Deployment package assembled and verified. Session READY.")

        except Exception as e:
            logger.exception("PreparationOrchestrator | Package generation failed.")
            try:
                db.rollback()
            except Exception as rollback_err:
                logger.error(f"PreparationOrchestrator | Database rollback failed: {rollback_err}")
            try:
                with UnitOfWork(db):
                    session_repository.update(db, session, SessionUpdate(status=SessionStatus.FAILED.value))
                    for j_type in ["VERIFICATION", "PACKAGE"]:
                        j = presentation_job_service.get_job_by_session(db, session_id=session_id, job_type=j_type)
                        if j and j.status != "COMPLETED":
                            presentation_job_service.update_job_status(db, j.id, status="FAILED", error_message=str(e))
            except Exception as update_err:
                logger.error(f"PreparationOrchestrator | Failed to update failure status: {update_err}")
            raise e
        finally:
            db.close()

preparation_orchestrator = PreparationOrchestrator()
