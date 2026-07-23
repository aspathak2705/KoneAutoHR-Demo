import time
import json
from pathlib import Path
from loguru import logger
from sqlalchemy.orm import Session as DBSession

from app.db.database import SessionLocal
from app.models.session import Session
from app.core.constants import JobStatus, SessionStatus
from app.repositories.session_repository import session_repository
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

    async def run_script_generation(self, session_id: str, trigger_job_id: str) -> None:
        """
        Coordinates Validation Pipeline, Parsing Pipeline, Context Builder, and Script Pipeline.
        """
        logger.info(f"PreparationOrchestrator | Starting script generation orchestration (Session: {session_id})")
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
                session_repository.update(db, session, status=SessionStatus.VALIDATING.value)
                presentation_job_service.update_job_status(db, val_job.id, status="PROCESSING", progress=0.1)

            val_report = validation_pipeline.execute(
                db, session.presentation_id, session.employee_list_id, session_id, session_dir
            )

            with UnitOfWork(db):
                presentation_job_service.update_job_status(db, val_job.id, status="COMPLETED", progress=1.0)

            # 2. Parsing Pipeline
            with UnitOfWork(db):
                session_repository.update(db, session, status=SessionStatus.PARSING.value)
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

            # 3. Context Builder
            structured_context = context_builder.build_context(
                db=db,
                session=session,
                slide_knowledge=parsed_data["slides"],
                employee_rows=parsed_data["employees"]
            )

            with open(session_dir / "structured_context.json", "w", encoding="utf-8") as f:
                json.dump(structured_context, f, indent=2)

            # 4. Script Pipeline
            with UnitOfWork(db):
                session_repository.update(db, session, status=SessionStatus.GENERATING_SCRIPT.value)
                presentation_job_service.update_job_status(db, script_job.id, status="PROCESSING", progress=0.1)

            await script_pipeline.execute(db, structured_context, session_dir)

            with UnitOfWork(db):
                session_repository.update(db, session, status=SessionStatus.UPLOADED.value)
                presentation_job_service.update_job_status(db, script_job.id, status="COMPLETED", progress=1.0)

            logger.info("PreparationOrchestrator | Script generation orchestration completed successfully.")

        except Exception as e:
            logger.exception("PreparationOrchestrator | Script generation failed.")
            with UnitOfWork(db):
                session_repository.update(db, session, status=SessionStatus.FAILED.value)
                for j_type in ["VALIDATION", "PARSING", "SCRIPT"]:
                    j = presentation_job_service.get_job_by_session(db, session_id=session_id, job_type=j_type)
                    if j and j.status != "COMPLETED":
                        presentation_job_service.update_job_status(db, j.id, status="FAILED", error_message=str(e))
        finally:
            db.close()

    async def run_audio_generation(self, session_id: str, trigger_job_id: str) -> None:
        """
        Coordinates Speech Pipeline, Asset Pipeline, Verification Pipeline, and Package Builder.
        """
        logger.info(f"PreparationOrchestrator | Starting audio generation orchestration (Session: {session_id})")
        db = SessionLocal()
        try:
            session = db.query(Session).filter(Session.id == session_id).first()
            if not session:
                logger.error(f"PreparationOrchestrator | Session {session_id} not found.")
                return

            audio_job = self._get_or_create_job(db, session_id, "AUDIO")
            pack_job = self._get_or_create_job(db, session_id, "PACKAGE")
            ver_job = self._get_or_create_job(db, session_id, "VERIFICATION")

            with UnitOfWork(db):
                presentation_job_service.update_job_status(db, audio_job.id, status="PENDING", progress=0.0)
                presentation_job_service.update_job_status(db, pack_job.id, status="PENDING", progress=0.0)
                presentation_job_service.update_job_status(db, ver_job.id, status="PENDING", progress=0.0)

            session_dir = storage_service.get_session_dir(session_id)
            
            with open(session_dir / "structured_context.json", "r", encoding="utf-8") as f:
                structured_context = json.load(f)
            with open(session_dir / "session_script.json", "r", encoding="utf-8") as f:
                script_data = json.load(f)
            with open(session_dir / "validation_report.json", "r", encoding="utf-8") as f:
                validation_report = json.load(f)

            # 5. Speech Pipeline (TTS)
            with UnitOfWork(db):
                session_repository.update(db, session, status=SessionStatus.GENERATING_AUDIO.value)
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
                session_repository.update(db, session, status=SessionStatus.REGISTERING_ASSETS.value)
                
            audio_manifest = asset_pipeline.execute(
                db=db,
                presentation_id=session.presentation_id,
                session_id=session_id,
                audio_tracks=audio_tracks,
                session_dir=session_dir
            )

            # 7. Verification Pipeline
            with UnitOfWork(db):
                session_repository.update(db, session, status=SessionStatus.VERIFYING.value)
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
                session_repository.update(db, session, status=SessionStatus.READY.value)
                presentation_job_service.update_job_status(db, pack_job.id, status="COMPLETED", progress=1.0)

            logger.info("PreparationOrchestrator | Deployment package assembled and verified. Session READY.")

        except Exception as e:
            logger.exception("PreparationOrchestrator | Audio/Package generation failed.")
            with UnitOfWork(db):
                session_repository.update(db, session, status=SessionStatus.FAILED.value)
                for j_type in ["AUDIO", "VERIFICATION", "PACKAGE"]:
                    j = presentation_job_service.get_job_by_session(db, session_id=session_id, job_type=j_type)
                    if j and j.status != "COMPLETED":
                        presentation_job_service.update_job_status(db, j.id, status="FAILED", error_message=str(e))
        finally:
            db.close()

preparation_orchestrator = PreparationOrchestrator()
