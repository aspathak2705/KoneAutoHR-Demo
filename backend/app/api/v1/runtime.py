import asyncio
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session as DBSession
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from app.db.database import get_db
from app.services.runtime_service import runtime_service
from app.services.session_service import session_service
from app.services.meeting_runtime_service import meeting_runtime_service
from app.services.teams_runtime_service import teams_runtime_service
from app.services.speech_runtime import speech_runtime_service
from app.services.qa_service import qa_service
from app.services.report_service import report_service
from app.models.runtime_message import RuntimeMessage
from app.models.organization_config import OrganizationConfig

from app.services.runtime_scheduler_service import runtime_scheduler_service
from app.services.runtime_validation_service import runtime_validation_service
from app.modules.meeting_bot.services.meeting_bot_service import meeting_bot_service
from app.modules.induction_runtime.models.runtime_state import RuntimeState
from loguru import logger

router = APIRouter(prefix="/runtime", tags=["Orchestration Runtime"])

# ============================================================================
# LOCKED LIFECYCLE ENDPOINTS - NEW ARCHITECTURE
# ============================================================================

@router.post("/{session_id}/prepare")
async def prepare_runtime(session_id: str, db: DBSession = Depends(get_db)):
    """
    Lifecycle Phase 1: NOT_CREATED -> PREPARING -> READY
    
    Button: "Prepare Runtime"
    Responsibilities:
    - Create Runtime entry
    - Load Configuration
    - Verify Assets (presentation, script, faq)
    - Verify Meeting URL
    - Verify Browser Installation
    - Register Runtime in READY state
    """
    logger.info(f"API | START POST /prepare for session {session_id}")
    try:
        # Create runtime and coordinator
        coordinator = runtime_service.create_runtime_and_coordinator(db, session_id)
        
        # Prepare runtime (PREPARING -> READY)
        if not await coordinator.prepare_runtime():
            raise HTTPException(status_code=400, detail="Failed to prepare runtime")

        logger.info(f"API | SUCCESS POST /prepare - runtime READY")
        return {
            "message": "Runtime prepared successfully",
            "state": "READY",
            "session_id": session_id
        }
    except Exception as e:
        logger.error(f"API | FAILED POST /prepare: {e}")
        raise HTTPException(status_code=400, detail=str(e))

class StartInductionRequest(BaseModel):
    force: bool = False

@router.post("/{session_id}/start-induction")
async def start_induction(
    session_id: str,
    req: Optional[StartInductionRequest] = None,
    db: DBSession = Depends(get_db)
):
    """
    Overloaded start-induction endpoint:
    - Phase 2: READY -> STARTING -> BROWSER_READY (Starts browser)
    - Phase 4: CONNECTED -> PRESENTING (Starts presentation after independent readiness validation)
    """
    logger.info(f"API | POST /start-induction for session {session_id}")
    try:
        from app.services.meeting_status_service import meeting_status_service
        coordinator = runtime_service.get_coordinator(db, session_id)
        
        if coordinator.session_manager.state == RuntimeState.PRESENTING:
            # Check if presentation is genuinely running vs stuck in failed state
            is_genuinely_running = (
                getattr(coordinator, "induction_started", False) and
                (
                    getattr(coordinator, "narration_state", "idle") not in ["idle", "failed"] or
                    (hasattr(coordinator, "_greeting_task") and coordinator._greeting_task is not None and not coordinator._greeting_task.done()) or
                    getattr(getattr(coordinator, "memory", None), "current_slide_number", 0) > 0
                )
            )
            if is_genuinely_running:
                logger.warning("API | Presentation is already running. Skipping duplicate trigger.")
                return {
                    "status": "success",
                    "message": "Presentation already running",
                    "state": "PRESENTING",
                    "session_id": session_id
                }
            else:
                logger.warning(f"API | Session {session_id} in PRESENTING state without active narration. Resetting to CONNECTED for safe retry.")
                await coordinator.session_manager.transition_to(RuntimeState.CONNECTED)

        # Check current state to determine action
        if coordinator.session_manager.state == RuntimeState.CONNECTED:
            # Independent backend readiness evaluation for hard prerequisites
            readiness = await meeting_status_service.evaluate_status(db, session_id)
            
            hard_blockers = []
            if not readiness.get("meeting_connected"):
                hard_blockers.append("Waiting for bot to connect to Microsoft Teams meeting.")
            if not readiness.get("runtime_assets_ready"):
                hard_blockers.append("Runtime presentation assets incomplete. Please verify Step 4.")
            if not readiness.get("audio_ready"):
                hard_blockers.append("Audio narration assets not ready. Please verify audio generation in Step 3.")
            
            if hard_blockers:
                blocked_str = "; ".join(hard_blockers)
                logger.warning(f"API | Start induction rejected (409 Conflict): {blocked_str}")
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={
                        "message": f"Induction cannot start: {blocked_str}",
                        "blocked_reasons": hard_blockers,
                        "checklist": readiness.get("checklist")
                    }
                )

            # Case A: If presentation is ALREADY detected, proceed directly with existing flow
            if readiness.get("presentation_detected"):
                try:
                    coordinator.induction_started = True
                    greeting_task = asyncio.create_task(coordinator._run_greeting_flow())
                    coordinator._greeting_task = greeting_task
                    await coordinator.session_manager.transition_to(RuntimeState.PRESENTING)
                    logger.info(f"API | Presentation already detected. Induction flow triggered for session {session_id}")
                    return {
                        "status": "success",
                        "auto_shared": False,
                        "presentation_detected": True,
                        "message": "Presentation active. Induction presentation started.",
                        "state": "PRESENTING",
                        "session_id": session_id,
                        "checklist": readiness.get("checklist")
                    }
                except Exception as start_err:
                    logger.error(f"API | Failed to dispatch greeting flow: {start_err}")
                    await coordinator.session_manager.transition_to(RuntimeState.CONNECTED)
                    raise HTTPException(status_code=500, detail=f"Failed to start greeting flow: {start_err}")

            # Case B: Presentation not yet shared. Authorize induction and initiate PowerPoint launch & auto-share
            from app.services.storage_service import storage_service
            import json
            coordinator.induction_started = True

            # 1. Identify PPTX path
            session_dir = storage_service.get_session_dir(session_id)
            manifest_path = session_dir / "manifest.json"
            ppt_path = None
            if manifest_path.exists():
                try:
                    with open(manifest_path, "r", encoding="utf-8") as f:
                        m = json.load(f)
                    pres_name = m.get("presentation", "presentation.pptx")
                    for candidate in [
                        session_dir / pres_name,
                        session_dir / "presentation" / pres_name,
                        session_dir / "presentation.pptx",
                        session_dir / "presentation" / "presentation.pptx"
                    ]:
                        if candidate.exists():
                            ppt_path = candidate
                            break
                except Exception as ex:
                    logger.warning(f"API | Error reading manifest presentation path: {ex}")

            if not ppt_path or not ppt_path.exists():
                try:
                    from app.models.session import Session as DBSessionModel
                    from app.core.security.secure_storage import secure_storage
                    import shutil
                    sess = db.query(DBSessionModel).filter(DBSessionModel.id == session_id).first()
                    if sess and sess.presentation:
                        with secure_storage.open_decrypted_file(sess.presentation) as dec_p:
                            fallback_path = session_dir / "presentation.pptx"
                            shutil.copy2(dec_p, fallback_path)
                            ppt_path = fallback_path
                except Exception as ex:
                    logger.warning(f"API | Fallback PPT retrieval error: {ex}")

            if not ppt_path or not ppt_path.exists():
                logger.error(f"API | PowerPoint file not found for session {session_id}")
                raise HTTPException(
                    status_code=404,
                    detail=f"PowerPoint file for session {session_id} not found on disk."
                )

            # 2. Open PowerPoint in slideshow mode
            ppt_opened = False
            ppt_error = None
            try:
                from app.modules.presentation.powerpoint_controller import PowerPointController
                ppt_ctrl = PowerPointController()
                await ppt_ctrl.open(str(ppt_path), start_immediately=True)
                ppt_opened = await ppt_ctrl.wait_for_slideshow_window(timeout=10.0)
                logger.info(f"API | PowerPoint slideshow opened for session {session_id}")
            except Exception as ppt_ex:
                ppt_error = str(ppt_ex)
                logger.warning(f"API | PowerPoint automation notice: {ppt_ex}")

            # 3. Attempt automatic Teams screen sharing via bot browser page
            auto_share_success = False
            from app.modules.meeting_bot.services.meeting_bot_service import meeting_bot_service
            bot = meeting_bot_service.get_bot(session_id)
            page = bot.context.page if bot and bot.context else None

            if ppt_opened and page and not page.is_closed():
                try:
                    from app.modules.meeting_bot.teams.teams_controller import teams_controller
                    from app.modules.presentation.native_share_controller import NativeShareController
                    from app.modules.presentation.share_verification_controller import ShareVerificationController

                    t_ctrl = teams_controller
                    native_share = NativeShareController()
                    verification = ShareVerificationController()

                    await t_ctrl.open_share_panel(page)
                    await native_share.activate_picker()
                    await native_share.click_window_tab()
                    await native_share.select_window("PowerPoint Slide Show", presentation_name=ppt_path.name)
                    await native_share.click_share()

                    auto_share_success = await verification.wait_for_share_confirmation(page, timeout=8.0)
                    logger.info(f"API | Automatic screen share result: {auto_share_success}")
                except Exception as share_ex:
                    logger.warning(f"API | Automatic Teams sharing attempt failed or timed out: {share_ex}")
                    try:
                        await page.keyboard.press("Escape")
                    except Exception:
                        pass
                    auto_share_success = False

            # 4. Check if auto sharing succeeded and presentation is now detected
            if auto_share_success:
                try:
                    from app.modules.presentation_observer.services.presentation_observer_service import presentation_observer_service
                    obs = await presentation_observer_service.run_observation_cycle(session_id)
                    if obs and obs.presentation_state in ["POWERPOINT_SHARED", "SCREEN_SHARING"]:
                        try:
                            greeting_task = asyncio.create_task(coordinator._run_greeting_flow())
                            coordinator._greeting_task = greeting_task
                            await coordinator.session_manager.transition_to(RuntimeState.PRESENTING)
                            return {
                                "status": "success",
                                "auto_shared": True,
                                "presentation_detected": True,
                                "message": "PowerPoint launched and screen shared automatically. Induction started.",
                                "state": "PRESENTING",
                                "session_id": session_id
                            }
                        except Exception as start_err:
                            logger.error(f"API | Failed to dispatch greeting flow: {start_err}")
                            await coordinator.session_manager.transition_to(RuntimeState.CONNECTED)
                            raise HTTPException(status_code=500, detail=f"Failed to start greeting flow: {start_err}")
                except Exception as obs_err:
                    logger.warning(f"API | Immediate observation cycle notice: {obs_err}")

                return {
                    "status": "waiting_presentation",
                    "auto_shared": True,
                    "presentation_detected": False,
                    "message": "PowerPoint slideshow opened and shared in Teams. Waiting for presentation screen detection...",
                    "state": "CONNECTED",
                    "session_id": session_id
                }

            # 5. Fallback: Auto share unavailable/failed, but PPT is open (or manual launch required)
            msg = (
                "PowerPoint is open in slideshow mode. Automatic Teams screen sharing was unavailable. "
                "Please share the PowerPoint Slide Show window or your screen manually."
            )
            if not ppt_opened and ppt_error:
                msg = f"Please open the PowerPoint presentation in slideshow mode and share it in Teams ({ppt_error})."

            return {
                "status": "manual_share_required",
                "auto_shared": False,
                "presentation_detected": False,
                "message": msg,
                "state": "CONNECTED",
                "session_id": session_id
            }
        elif coordinator.session_manager.state == RuntimeState.READY:
            if not await coordinator.start_induction():
                raise HTTPException(
                    status_code=400,
                    detail="Failed to start induction"
                )
            return {
                "message": "Induction started, browser ready",
                "state": "BROWSER_READY",
                "session_id": session_id
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Cannot start induction from current state: {coordinator.session_manager.state.value}. Expected READY or CONNECTED."
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"API | FAILED POST /start-induction: {e}")
        raise HTTPException(status_code=400, detail=str(e))

class JoinMeetingRequest(BaseModel):
    meeting_url: Optional[str] = None
    display_name: Optional[str] = None

@router.post("/{session_id}/join-meeting")
async def join_meeting_endpoint(session_id: str, req: Optional[JoinMeetingRequest] = None, db: DBSession = Depends(get_db)):
    """
    Lifecycle Phase 3: BROWSER_READY -> JOINING -> WAITING -> CONNECTED
    """
    logger.info(f"API | START POST /join-meeting for session {session_id}")
    try:
        coordinator = runtime_service.get_coordinator(db, session_id)
        
        # Get custom link from request body first, fallback to context
        meeting_url = req.meeting_url if req else None
        if not meeting_url:
            context = runtime_service.get_runtime_context(db, session_id)
            meeting_url = context.get("meeting", {}).get("teams_meeting_url")
        
        if not meeting_url:
            raise HTTPException(status_code=400, detail="Meeting URL not found")
        
        display_name = req.display_name if req else None
        if not display_name:
            context = runtime_service.get_runtime_context(db, session_id)
            display_name = context.get("persona", {}).get("ai_trainer_name") or "KONE AI Trainer"

        # Join meeting
        try:
            join_success = await coordinator.join_meeting(meeting_url, display_name)
        except Exception as join_err:
            import traceback
            tb = traceback.format_exc()
            logger.error(f"API | Exception in coordinator.join_meeting for session {session_id}: {join_err}\nTraceback:\n{tb}")
            raise HTTPException(
                status_code=400,
                detail="Failed to join Microsoft Teams meeting. Please verify meeting URL and ensure call is active."
            )

        if not join_success:
            last_err = getattr(coordinator.session_manager, "failure_reason", None) or "Teams join timed out or prejoin controls not detected"
            logger.error(f"API | join_meeting returned False for session {session_id}: {last_err}")
            raise HTTPException(
                status_code=400,
                detail="Failed to join Microsoft Teams meeting. Prejoin controls not detected or join timed out."
            )
        
        logger.info(f"API | SUCCESS POST /join-meeting - CONNECTED")
        return {
            "message": "Joined meeting successfully",
            "state": "CONNECTED",
            "session_id": session_id
        }
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        logger.error(f"API | FAILED POST /join-meeting: {e}\nTraceback:\n{tb}")
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/{session_id}/end")
async def end_runtime(session_id: str, db: DBSession = Depends(get_db)):
    """
    Lifecycle Phase Final: Any state -> FINISHING -> STOPPED
    
    Button: "End Session"
    Responsibilities:
    - Leave meeting
    - Stop presentation
    - Cleanup resources in reverse order
    - Transition to STOPPED
    """
    logger.info(f"API | START POST /end for session {session_id}")
    try:
        coordinator = runtime_service.get_coordinator(db, session_id)
        
        # Finish presentation and cleanup
        if not await coordinator.finish_presentation():
            raise HTTPException(status_code=400, detail="Failed to finish presentation")
        
        # Remove from cache
        runtime_service.remove_coordinator(session_id)
        
        logger.info(f"API | SUCCESS POST /end - STOPPED")
        return {
            "message": "Runtime stopped successfully",
            "state": "STOPPED",
            "session_id": session_id
        }
    except Exception as e:
        logger.error(f"API | FAILED POST /end: {e}")
        raise HTTPException(status_code=400, detail=str(e))

# ============================================================================
# LEGACY ENDPOINTS (kept for backward compatibility during migration)
# ============================================================================

@router.post("/{session_id}/schedule")
def schedule_runtime_meeting(session_id: str, db: DBSession = Depends(get_db)):
    try:
        return runtime_scheduler_service.schedule_session(db, session_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/{session_id}/schedule")
def get_runtime_schedule(session_id: str, db: DBSession = Depends(get_db)):
    try:
        return runtime_scheduler_service.get_schedule_status(db, session_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/{session_id}/validate")
def validate_runtime(session_id: str, db: DBSession = Depends(get_db)):
    try:
        return runtime_validation_service.validate_runtime_readiness(db, session_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/{session_id}/phase2b-handover")
def get_phase2b_handover_context(session_id: str, db: DBSession = Depends(get_db)):
    try:
        db_runtime = meeting_runtime_service.get_runtime(db, session_id)
        if db_runtime.state not in ["CONNECTED", "WAITING", "COMPLETED"]:
            raise HTTPException(
                status_code=400,
                detail=f"Runtime not ready for Phase 2B handover. Current state is {db_runtime.state}. Must be CONNECTED & WAITING."
            )
        return {
            "handover_status": "READY",
            "runtime_state": db_runtime.state,
            "context": runtime_service.get_runtime_context(db, session_id)
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/{session_id}/summary")
def get_runtime_summary(session_id: str, db: DBSession = Depends(get_db)):
    try:
        context = runtime_service.get_runtime_context(db, session_id)
        readiness = runtime_validation_service.validate_runtime_readiness(db, session_id)
        db_runtime = meeting_runtime_service.get_runtime(db, session_id)
        status_val = db_runtime.state if db_runtime else "NOT_CREATED"

        # Check if active presentation is paused
        from app.modules.presentation.presentation_runtime_controller import get_active_presentation_controller
        active_pres = get_active_presentation_controller(session_id)
        if active_pres and active_pres._is_paused:
            status_val = "PAUSED"
        
        # Audio & Script count from presentation assets
        slides_info = runtime_service.get_slide_controller(db, session_id)
        total_slides = slides_info.get("total_slides", 0)
        
        return {
            "session_id": session_id,
            "session_name": context.get("session_name"),
            "presentation_name": context.get("presentation", {}).get("original_filename"),
            "total_slides": total_slides,
            "generated_audio_count": total_slides,
            "generated_script_count": total_slides,
            "runtime_status": status_val,
            "meeting_url": context.get("meeting", {}).get("teams_meeting_url"),
            "trainer": context.get("persona", {}).get("ai_trainer_name"),
            "employee_count": len(context.get("employees", [])),
            "voice": runtime_service.get_voice_config()
        }
    except Exception as e:
        logger.error(f"API | FAILED GET /summary: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/{session_id}/audio")
def get_runtime_audio_tracks(session_id: str, db: DBSession = Depends(get_db)):
    try:
        from app.services.storage_service import storage_service
        audio_dir = storage_service.get_session_dir(session_id) / "audio"
        tracks = []
        
        # Priority order of standard voiceover blocks
        standards = ["greeting.mp3", "intro.mp3", "closing.mp3"]
        for std in standards:
            if (audio_dir / std).exists():
                tracks.append(std)
                
        # Slides audio tracks (safely attempted if script is ready)
        try:
            slides_info = runtime_service.get_slide_controller(db, session_id)
            slides = slides_info.get("slides", [])
            for s in slides:
                slide_file = f"slide_{s['slide_number']}.mp3"
                if (audio_dir / slide_file).exists() and slide_file not in tracks:
                    tracks.append(slide_file)
        except (ValueError, Exception) as controller_err:
            logger.debug(f"API | Slide controller not yet populated for session {session_id}: {controller_err}")
                
        # Fallback directory scanner for any other generated audios
        if audio_dir.exists():
            for f in audio_dir.iterdir():
                if f.is_file() and f.suffix.lower() == ".mp3" and f.name not in tracks:
                    tracks.append(f.name)
                    
        return tracks
    except Exception as e:
        logger.error(f"API | Failed to list audio tracks: {e}")
        return []

@router.post("/{session_id}/audio/play")
async def play_runtime_audio_track(session_id: str, req: Dict[str, str]):
    track = req.get("track")
    if not track:
        raise HTTPException(status_code=400, detail="Missing track field")
    try:
        await meeting_bot_service.play_audio(track, session_id)
        return {"status": "success", "track": track}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/{session_id}/audio/stop")
async def stop_runtime_audio_track(session_id: str):
    try:
        await meeting_bot_service.stop_audio(session_id)
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

class AskQuestionRequest(BaseModel):
    speaker_name: str
    question_text: str

class SpeakRequest(BaseModel):
    narration_text: str

class MessageResponse(BaseModel):
    id: str
    session_id: str
    speaker_name: str
    message_text: str
    timestamp: str

    class Config:
        from_attributes = True

@router.get("/{session_id}/context")
def get_runtime_context(session_id: str, db: DBSession = Depends(get_db)):
    try:
        return runtime_service.get_runtime_context(db, session_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.get("/{session_id}/voice-config")
def get_voice_config(session_id: str, db: DBSession = Depends(get_db)):
    return runtime_service.get_voice_config()

@router.get("/{session_id}/slide-controller")
def get_slide_controller(session_id: str, db: DBSession = Depends(get_db)):
    try:
        return runtime_service.get_slide_controller(db, session_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

from app.services.runtime_context_service import runtime_context_service
from app.services.runtime_readiness_service import runtime_readiness_service

@router.get("/readiness/{session_id}")
def get_unified_runtime_readiness(session_id: str, db: DBSession = Depends(get_db)):
    """
    Phase 4 -- Unified Readiness API
    Returns authoritative, single-source-of-truth readiness report for a session with HTTP 200 OK.
    Never returns HTTP 400 for missing assets.
    """
    context = runtime_context_service.build_runtime_context(db, session_id)
    return runtime_readiness_service.evaluate_readiness(context)

@router.get("/{session_id}/status")
def get_runtime_status_detailed(session_id: str, db: DBSession = Depends(get_db)):
    """
    Sprint RC-1: Returns detailed connection state logs.
    """
    return teams_runtime_service.get_status(db, session_id)

@router.get("/{session_id}/meeting-status")
async def get_meeting_status_endpoint(session_id: str, db: DBSession = Depends(get_db)):
    """
    Returns aggregated live meeting status and readiness metrics.
    """
    try:
        from app.services.meeting_status_service import meeting_status_service
        status = await meeting_status_service.evaluate_status(db, session_id)
        return status
    except Exception as e:
        logger.error(f"API | Failed to evaluate meeting status: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/{session_id}")
def get_runtime_status(session_id: str, db: DBSession = Depends(get_db)):
    """
    Sprint 3 & 4: Returns running meeting status combined with readiness and QA counters.
    Never fails with 400 if session assets are not fully ready.
    """
    context = runtime_context_service.build_runtime_context(db, session_id)
    readiness = runtime_readiness_service.evaluate_readiness(context)

    db_runtime = meeting_runtime_service.get_runtime(db, session_id)
    state = db_runtime.state if db_runtime else "IDLE"
    if session_id not in runtime_service._coordinators:
        state = "NOT_CREATED"
    current_slide = db_runtime.current_slide if db_runtime else 0
    reconnect_count = db_runtime.reconnect_count if db_runtime else 0
    speech_state = db_runtime.speech_state if db_runtime else "IDLE"
    last_hb = db_runtime.last_heartbeat.isoformat() if db_runtime and db_runtime.last_heartbeat else None

    # Fetch question speaker count
    config = db.query(OrganizationConfig).first()
    trainer = config.ai_trainer_name if config else "KONE Trainer"
    questions = db.query(RuntimeMessage).filter(
        RuntimeMessage.session_id == session_id,
        RuntimeMessage.speaker_name != trainer
    ).all()

    narration_state = "idle"
    if session_id in runtime_service._coordinators:
        narration_state = runtime_service._coordinators[session_id].narration_state

    return {
        "session_id": session_id,
        "state": state,
        "current_slide": current_slide,
        "reconnect_count": reconnect_count,
        "speech_state": speech_state,
        "last_heartbeat": last_hb,
        "last_error": db_runtime.last_error if db_runtime else None,
        "questions_asked": len(questions),
        "presentation_ready": readiness.get("has_presentation") and readiness.get("has_script") and readiness.get("has_faq"),
        "employees_ready": readiness.get("has_employees"),
        "meeting_ready": readiness.get("has_meeting"),
        "ai_ready": readiness.get("has_script") and readiness.get("has_faq"),
        "readiness_report": readiness,
        "narration_state": narration_state
    }

# Legacy launch/join/leave endpoints removed since they are unused

@router.post("/{session_id}/presentation/pause")
@router.post("/{session_id}/pause")
async def pause_runtime_presentation(session_id: str):
    """
    Pauses active presentation and narration playback.
    Keeps Teams bot in meeting and PowerPoint slideshow running.
    """
    from app.modules.presentation.presentation_runtime_controller import get_active_presentation_controller
    controller = get_active_presentation_controller(session_id)
    if not controller:
        # Fallback to session interpreter if running in legacy mode
        try:
            from app.modules.session.session_interpreter import get_session_interpreter
            interpreter = get_session_interpreter(session_id)
            interpreter.pause_session()
            return {"status": "success", "message": f"Session interpreter paused for {session_id}"}
        except Exception:
            raise HTTPException(status_code=404, detail="No active presentation controller found for session")

    await controller.pause()
    return {"status": "success", "message": f"Presentation and narration paused for session {session_id}"}

@router.post("/{session_id}/presentation/resume")
@router.post("/{session_id}/resume")
async def resume_runtime_presentation(session_id: str):
    """
    Resumes paused presentation and narration playback from exact ms position.
    """
    from app.modules.presentation.presentation_runtime_controller import get_active_presentation_controller
    controller = get_active_presentation_controller(session_id)
    if not controller:
        try:
            from app.modules.session.session_interpreter import get_session_interpreter
            interpreter = get_session_interpreter(session_id)
            interpreter.resume_session()
            return {"status": "success", "message": f"Session interpreter resumed for {session_id}"}
        except Exception:
            raise HTTPException(status_code=404, detail="No active presentation controller found for session")

    await controller.resume()
    return {"status": "success", "message": f"Presentation and narration resumed for session {session_id}"}

@router.post("/{session_id}/speak")
async def start_runtime_speaking(session_id: str, req: SpeakRequest):
    speech_runtime_service.speak(session_id, req.narration_text)
    return {"message": "TTS speaking initiated."}

@router.post("/{session_id}/stop-speaking")
async def stop_runtime_speaking(session_id: str):
    speech_runtime_service.stop_speaking(session_id)
    return {"message": "TTS speaking interrupted."}

@router.post("/{session_id}/start")
async def start_runtime(session_id: str, db: DBSession = Depends(get_db)):
    meeting_runtime_service.start_meeting(session_id)
    return {"message": "AI meeting orchestration session launched."}

@router.post("/{session_id}/stop")
async def stop_runtime(session_id: str, db: DBSession = Depends(get_db)):
    meeting_runtime_service.stop_meeting(session_id)
    return {"message": "AI meeting orchestration session stopped."}

@router.post("/{session_id}/next")
async def advance_runtime_slide(session_id: str, db: DBSession = Depends(get_db)):
    new_slide = await meeting_runtime_service.advance_slide(session_id)
    return {"current_slide": new_slide}

@router.post("/{session_id}/prev")
async def previous_runtime_slide(session_id: str, db: DBSession = Depends(get_db)):
    new_slide = await meeting_runtime_service.previous_slide(session_id)
    return {"current_slide": new_slide}

@router.post("/{session_id}/ask")
async def ask_attendee_question(session_id: str, req: AskQuestionRequest, db: DBSession = Depends(get_db)):
    try:
        coordinator = runtime_service.get_coordinator(db, session_id)
        answer = await coordinator.inject_question(req.speaker_name, req.question_text)

        config = db.query(OrganizationConfig).first()
        trainer = config.ai_trainer_name if config else "KONE Trainer"
        return {
            "question": {
                "speaker": req.speaker_name,
                "text": req.question_text
            },
            "answer": {
                "speaker": trainer,
                "text": answer
            }
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.get("/{session_id}/conversation")
def get_conversation_history(session_id: str, db: DBSession = Depends(get_db)):
    history = qa_service.get_conversation_history(db, session_id)
    return [
        {
            "id": msg.id,
            "session_id": msg.session_id,
            "speaker_name": msg.speaker_name,
            "message_text": msg.message_text,
            "timestamp": msg.timestamp.isoformat()
        }
        for msg in history
    ]

@router.get("/{session_id}/report")
def download_session_report(session_id: str, db: DBSession = Depends(get_db)):
    try:
        report_path, _ = report_service.generate_and_save_packages(db, session_id)
        if not report_path.exists():
            raise HTTPException(status_code=404, detail="Report file not found")
        return FileResponse(
            path=report_path,
            filename=f"induction_report_{session_id}.md",
            media_type="text/markdown"
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/{session_id}/report.pdf")
def download_session_report_pdf(session_id: str, db: DBSession = Depends(get_db)):
    try:
        pdf_path = report_service.get_or_generate_pdf(db, session_id)
        if not pdf_path.exists():
            raise HTTPException(status_code=404, detail="PDF report not found")
        return FileResponse(
            path=pdf_path,
            filename=f"kone_induction_report_{session_id}.pdf",
            media_type="application/pdf"
        )
    except Exception as e:
        logger.error(f"Runtime | Failed to generate/serve PDF report: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/{session_id}/report.docx")
def download_session_report_docx(session_id: str, db: DBSession = Depends(get_db)):
    try:
        docx_path = report_service.get_or_generate_docx(db, session_id)
        if not docx_path.exists():
            raise HTTPException(status_code=404, detail="Word report not found")
        return FileResponse(
            path=docx_path,
            filename=f"kone_induction_report_{session_id}.docx",
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
    except Exception as e:
        logger.error(f"Runtime | Failed to generate/serve DOCX report: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/{session_id}/transcript")
def download_session_transcript(session_id: str, db: DBSession = Depends(get_db)):
    try:
        _, transcript_path = report_service.generate_and_save_packages(db, session_id)
        if not transcript_path.exists():
            raise HTTPException(status_code=404, detail="Transcript file not found")
        return FileResponse(
            path=transcript_path,
            filename=f"induction_transcript_{session_id}.md",
            media_type="text/markdown"
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/{session_id}/presentation-file")
def download_session_presentation(session_id: str, db: DBSession = Depends(get_db)):
    """
    Downloads the generated presentation.pptx file for the session.
    """
    from app.services.storage_service import storage_service
    session_dir = storage_service.get_session_dir(session_id)
    ppt_path = session_dir / "presentation.pptx"
    if not ppt_path.exists():
        ppt_path = session_dir / "presentation" / "presentation.pptx"
    if not ppt_path.exists():
        # Fallback to presentation registered in session
        runtime_context = runtime_service.get_runtime_context(db, session_id)
        candidate = runtime_context.get("presentation", {}).get("storage_path")
        if candidate and Path(candidate).exists():
            ppt_path = Path(candidate)

    if not ppt_path.exists():
        raise HTTPException(status_code=404, detail="Generated presentation file not found")

    return FileResponse(
        path=ppt_path,
        filename=f"kone_presentation_{session_id}.pptx",
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation"
    )

@router.get("/{session_id}/attendance")
def get_attendance_report(session_id: str, db: DBSession = Depends(get_db)):
    from app.services.attendance_service import attendance_service
    return attendance_service.get_attendance_summary(db, session_id)

@router.get("/{session_id}/transcript-data")
def get_transcript_raw(session_id: str, db: DBSession = Depends(get_db)):
    from app.services.transcript_service import transcript_service
    return transcript_service.get_chronological_transcript(db, session_id)

@router.post("/{session_id}/reconnect")
async def trigger_reconnect_simulation(session_id: str):
    from app.services.teams_runtime_service import teams_runtime_service
    await teams_runtime_service.simulate_reconnect(session_id)
    return {"message": "Reconnection sequence triggered."}

@router.get("/audio/devices")
def get_audio_devices():
    """
    QA-010: Detect host audio devices and verify VB-Audio Virtual Cable availability.
    """
    try:
        import sounddevice as sd
        devices = sd.query_devices()
        cable_inputs = []
        cable_outputs = []
        all_devs = []

        for idx, dev in enumerate(devices):
            name = dev.get("name", "")
            max_in = dev.get("max_input_channels", 0)
            max_out = dev.get("max_output_channels", 0)
            dev_info = {
                "id": idx,
                "name": name,
                "input_channels": max_in,
                "output_channels": max_out,
                "is_cable": "cable" in name.lower() or "vb-audio" in name.lower()
            }
            all_devs.append(dev_info)

            if "cable" in name.lower() or "vb-audio" in name.lower():
                if max_out > 0:
                    cable_inputs.append(dev_info)  # "CABLE Input" receives output audio from AutoHR
                if max_in > 0:
                    cable_outputs.append(dev_info) # "CABLE Output" feeds into Teams microphone

        has_cable = len(cable_inputs) > 0 or len(cable_outputs) > 0
        return {
            "status": "ready" if has_cable else "missing_cable",
            "has_cable": has_cable,
            "cable_inputs_found": len(cable_inputs),
            "cable_outputs_found": len(cable_outputs),
            "summary": "VB-Audio Virtual Cable detected. Ready for meeting audio routing." if has_cable else "VB-Audio Virtual Cable not detected. Please install VB-CABLE Driver to bridge audio to Teams.",
            "instructions": {
                "step_1": "Install VB-Audio Virtual Cable from vb-audio.com/Cable (free).",
                "step_2": "In AutoHR audio configuration, select 'CABLE Input' as the playback target.",
                "step_3": "In Microsoft Teams Device Settings, select 'CABLE Output' as the Microphone device."
            },
            "devices": all_devs
        }
    except Exception as e:
        logger.warning(f"Failed to query sound devices: {e}")
        return {
            "status": "unavailable",
            "has_cable": False,
            "error": str(e),
            "summary": "Audio device querying unavailable on host.",
            "devices": []
        }

@router.post("/audio/test-playback")
def test_audio_playback():
    """
    QA-010: Plays a short 440Hz test chime through VB-Audio Cable Input or default device to verify pipeline.
    """
    try:
        import sounddevice as sd
        import numpy as np

        sample_rate = 44100
        duration = 0.5  # 500ms
        t = np.linspace(0, duration, int(sample_rate * duration), False)
        # 440Hz tone with smooth decay
        tone = np.sin(440 * t * 2 * np.pi) * np.exp(-3 * t) * 0.25

        # Find CABLE Input device index if present
        devices = sd.query_devices()
        target_device = None
        for idx, dev in enumerate(devices):
            if ("cable input" in dev.get("name", "").lower() or "cable in" in dev.get("name", "").lower()) and dev.get("max_output_channels", 0) > 0:
                target_device = idx
                break

        if target_device is not None:
            sd.play(tone, sample_rate, device=target_device)
            target_name = devices[target_device].get("name", "CABLE Input")
        else:
            sd.play(tone, sample_rate)
            target_name = "Default System Audio"

        return {
            "status": "success",
            "device_used": target_name,
            "message": f"Test chime played successfully through '{target_name}'."
        }
    except Exception as e:
        logger.warning(f"Audio test playback failed: {e}")
        return {
            "status": "failed",
            "error": str(e),
            "message": f"Playback failed: {e}"
        }


