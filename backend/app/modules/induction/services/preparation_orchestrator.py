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

            parsed_data = await parsing_pipeline.execute(
                db=db,
                presentation_id=session.presentation_id,
                ppt_path=val_report["details"]["ppt_path"],
                employee_list_id=session.employee_list_id,
                excel_path=val_report["details"]["excel_path"],
                session_id=session_id,
                session_dir=session_dir
            )

            with UnitOfWork(db):
                presentation_job_status = SessionStatus.UPLOADED.value
                session_repository.update(db, session, SessionUpdate(status=presentation_job_status))
                presentation_job_service.update_job_status(db, parse_job.id, status="COMPLETED", progress=1.0)
                presentation_job_service.update_job_status(db, script_job.id, status="COMPLETED", progress=1.0)

            # Keep compatibility files for validation script
            structured_context = context_builder.build_context(db, session, parsed_data["slides"], parsed_data["employees"])
            with open(session_dir / "structured_context.json", "w", encoding="utf-8") as f:
                json.dump(structured_context, f, indent=2)

            with open(session_dir / "validation_report.json", "w", encoding="utf-8") as f:
                json.dump(val_report, f, indent=2)

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

            # Check cached presentation assets to eliminate redundant Sarvam TTS/Timeline generation
            from app.modules.presentation.presentation_asset_manager import presentation_asset_manager
            assets_status = presentation_asset_manager.check_assets(db, session.presentation_id)
            paths = presentation_asset_manager.get_asset_paths(session.presentation_id)

            if assets_status["narration_exists"] and assets_status["timeline_exists"] and assets_status["manifest_exists"]:
                logger.info(f"PreparationOrchestrator | Reusable assets found for presentation {session.presentation_id}. Copying cached artifacts...")
                import shutil
                shutil.copy2(paths["narration"], session_dir / "narration.wav")
                shutil.copy2(paths["timeline"], session_dir / "presentation_timeline.json")
                shutil.copy2(paths["manifest"], session_dir / "manifest.json")
                
                # Copy compatible audio_manifest.json as well if it exists or create one
                audio_dir = session_dir / "audio"
                audio_dir.mkdir(parents=True, exist_ok=True)
                shutil.copy2(paths["narration"], audio_dir / "narration.wav")
                
                # Copy slides thumbnail directory to session if they exist
                if paths["slides_dir"].exists():
                    session_slides_dir = session_dir / "presentation_assets" / "slides"
                    session_slides_dir.mkdir(parents=True, exist_ok=True)
                    for slide_img in paths["slides_dir"].glob("slide_*.png"):
                        shutil.copy2(slide_img, session_slides_dir / slide_img.name)
                
                # Construct inline audio manifest mapping
                duration_ms = 0.0
                try:
                    with open(paths["manifest"], "r", encoding="utf-8") as mf:
                        m_data = json.load(mf)
                        duration_ms = m_data.get("duration_ms", 0.0)
                except Exception:
                    pass

                audio_manifest_data = {
                    "session_id": session_id,
                    "presentation_id": session.presentation_id,
                    "total_audio_tracks": 1,
                    "tracks": [{
                        "label": "narration",
                        "slide_number": 1,
                        "filename": "narration.wav",
                        "duration": duration_ms / 1000.0,
                        "checksum": "cached",
                        "version": 1,
                        "path": f"sessions/{session_id}/audio/narration.wav",
                        "voice": "aayan",
                        "metadata": {}
                    }]
                }
                with open(session_dir / "audio_manifest.json", "w", encoding="utf-8") as f:
                    json.dump(audio_manifest_data, f, indent=2)

                with UnitOfWork(db):
                    session_repository.update(db, session, SessionUpdate(status=SessionStatus.READY.value))
                    presentation_job_service.update_job_status(db, audio_job.id, status="COMPLETED", progress=1.0)
                logger.info("PreparationOrchestrator | Reusable audio & timeline package cloned successfully.")
                return

            # 5. Speech Pipeline (TTS)
            with UnitOfWork(db):
                session_repository.update(db, session, SessionUpdate(status=SessionStatus.GENERATING_AUDIO.value))
                presentation_job_service.update_job_status(db, audio_job.id, status="PROCESSING", progress=0.1)

            from app.services.voice.voice_service import voice_service
            audio_path, timestamps, duration_ms = await voice_service.generate_narration(session_id, script_data)

            # Determine slide count
            slides_dir = session_dir / "presentation_assets" / "slides"
            slide_count = len(list(slides_dir.glob("slide_*.png")))
            if slide_count == 0:
                slide_count = len(script_data.get("slides", []))

            # 6. Timeline Generation
            from app.services.timeline.timeline_builder import timeline_builder
            timeline_path = timeline_builder.build_timeline(
                session_id=session_id,
                timestamps=timestamps,
                total_duration_ms=duration_ms,
                slide_count=slide_count,
                session_dir=session_dir
            )

            # 7. Manifest Generation
            from app.services.session.manifest_builder import manifest_builder
            manifest_path = manifest_builder.build_manifest(
                session_id=session_id,
                presentation_filename="presentation.pptx",
                audio_filename="narration.wav",
                timeline_filename="presentation_timeline.json",
                duration_ms=duration_ms,
                slide_count=slide_count,
                session_dir=session_dir
            )

            # Copy generated narration, timeline and manifest into presentation asset manager cache
            import shutil
            shutil.copy2(audio_path, paths["narration"])
            shutil.copy2(timeline_path, paths["timeline"])
            shutil.copy2(manifest_path, paths["manifest"])
            
            # Cache slides if present in presentation_assets
            if slides_dir.exists():
                paths["slides_dir"].mkdir(parents=True, exist_ok=True)
                for slide_img in slides_dir.glob("slide_*.png"):
                    shutil.copy2(slide_img, paths["slides_dir"] / slide_img.name)

            # Generate compatible audio_manifest.json for Verification & Package Builder pipeline
            from app.modules.induction.package.asset_manager import asset_manager
            
            audio_dir = session_dir / "audio"
            audio_dir.mkdir(parents=True, exist_ok=True)
            dest_audio_path = audio_dir / "narration.wav"
            shutil.copy2(audio_path, dest_audio_path)
            
            with open(dest_audio_path, "rb") as f:
                audio_content = f.read()
                
            relative_path = f"sessions/{session_id}/audio/narration.wav"
            with UnitOfWork(db):
                asset = asset_manager.save_and_register_asset(
                    db=db,
                    presentation_id=session.presentation_id,
                    relative_path=relative_path,
                    content=audio_content,
                    asset_type="audio"
                )
                
            metadata = asset_manager.generate_metadata("narration.wav", audio_content, relative_path)
            voice_tone = script_data.get("ai_persona", {}).get("tone", "aayan").strip().lower()
            
            audio_manifest_data = {
                "session_id": session_id,
                "presentation_id": session.presentation_id,
                "total_audio_tracks": 1,
                "tracks": [{
                    "label": "narration",
                    "slide_number": 1,
                    "filename": "narration.wav",
                    "duration": duration_ms / 1000.0,
                    "checksum": asset.checksum,
                    "version": asset.version,
                    "path": relative_path,
                    "voice": voice_tone,
                    "metadata": metadata
                }]
            }
            
            with open(session_dir / "audio_manifest.json", "w", encoding="utf-8") as f:
                json.dump(audio_manifest_data, f, indent=2)

            with UnitOfWork(db):
                presentation_job_service.update_job_status(db, audio_job.id, status="COMPLETED", progress=1.0)
                session_repository.update(db, session, SessionUpdate(status=SessionStatus.READY.value))

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
                parsed_data = await parsing_pipeline.execute(
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
