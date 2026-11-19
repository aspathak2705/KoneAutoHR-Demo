import asyncio
import time
from sqlalchemy.orm import Session as DBSession
from app.modules.meeting_bot.services.meeting_bot_service import meeting_bot_service
from app.modules.meeting_bot.teams.participant_monitor import participant_monitor
from app.modules.meeting_bot.media.audio_controller import get_audio_controller
from app.modules.presentation_observer.services.presentation_observer_service import presentation_observer_service
from app.modules.meeting_bot.bot.bot_state import BotState
from app.modules.induction_runtime.orchestrator.session_manager import RuntimeState
from app.modules.semantic_browser.models.presentation_state import PresentationMode
from app.services.runtime_service import runtime_service
from app.services.storage_service import storage_service
from app.models.session import Session as DBSessionModel
from app.models.runtime import Runtime as DBRuntimeModel
from loguru import logger
from typing import Dict, Any, List

class MeetingStatusService:
    def __init__(self):
        self._obs_locks: Dict[str, asyncio.Lock] = {}
        self._last_obs_time: Dict[str, float] = {}

    def _get_obs_lock(self, session_id: str) -> asyncio.Lock:
        if session_id not in self._obs_locks:
            self._obs_locks[session_id] = asyncio.Lock()
        return self._obs_locks[session_id]

    async def evaluate_status(self, db: DBSession, session_id: str) -> Dict[str, Any]:
        """
        Authoritative meeting readiness evaluator.
        Aggregates live meeting state, detects Teams connection, presentation sharing,
        audio readiness, and runtime package assets.
        Never throws 500 error on missing assets or disconnected calls.
        """
        bot = meeting_bot_service.get_bot(session_id)
        logger.info(
            f"MeetingStatusService | session_id: {session_id} | "
            f"bot exists: {bot is not None} | "
            f"page exists: {bot.context.page is not None if bot else False}"
        )
        
        meeting_connected = False
        participants = 0
        required_participants = 1
        presentation_detected = False
        audio_ready = False
        runtime_assets_ready = False
        raw_participants: List[str] = []

        # --------------------------------------------------------------------
        # 1. Evaluate Teams Meeting Connection & Participant Headcount
        # --------------------------------------------------------------------
        if bot and bot.context.page and not bot.context.page.is_closed():
            try:
                meeting_connected = await participant_monitor.meeting_active(bot.context.page)
                if not meeting_connected and getattr(bot.context, "state", None) == BotState.CONNECTED:
                    meeting_connected = True
                
                if meeting_connected:
                    raw_participants = await participant_monitor.get_participants(bot.context)
            except Exception as e:
                logger.error(f"MeetingStatusService | Failed to read Teams metrics: {e}")
                if getattr(bot.context, "state", None) == BotState.CONNECTED:
                    meeting_connected = True

        # Fallback to coordinator runtime state if active in memory
        if not meeting_connected and session_id in runtime_service._coordinators:
            coord = runtime_service._coordinators[session_id]
            if getattr(coord, "session_manager", None) and coord.session_manager.state in [
                RuntimeState.CONNECTED,
                RuntimeState.PRESENTING
            ]:
                meeting_connected = True

        # Fallback to database runtime record if marked connected
        if not meeting_connected and db:
            try:
                db_rt = db.query(DBRuntimeModel).filter(
                    DBRuntimeModel.session_id == session_id
                ).order_by(DBRuntimeModel.updated_at.desc()).first()
                if db_rt and db_rt.state in ["CONNECTED", "PRESENTING"]:
                    # Verify page is not explicitly closed
                    if bot and bot.context.page and not bot.context.page.is_closed():
                        meeting_connected = True
            except Exception as db_err:
                logger.debug(f"MeetingStatusService | DB runtime check failed: {db_err}")

        # Retrieve expected participant count from Session context
        try:
            ctx = runtime_service.get_runtime_context(db, session_id)
            required_participants = max(1, len(ctx.get("employees", [])))
        except Exception as e:
            logger.debug(f"MeetingStatusService | Defaulting required count due to lookup: {e}")

        # Exclude bot self-names from headcount
        filtered_participants = []
        for p in raw_participants:
            p_lower = p.lower().strip()
            if "kone ai" in p_lower or "bot" in p_lower:
                continue
            filtered_participants.append(p)

        participants = len(filtered_participants)
        participant_ready = True  # Attendees count is informational; does not block start

        # --------------------------------------------------------------------
        # 2. Evaluate Presentation Screen Sharing in Teams
        # --------------------------------------------------------------------
        try:
            obs = None
            if bot and bot.context.page and not bot.context.page.is_closed():
                now = time.time()
                last_time = self._last_obs_time.get(session_id, 0.0)
                lock = self._get_obs_lock(session_id)

                # Avoid concurrent or excessive observation work from repeated polling
                if (now - last_time < 2.5) or lock.locked():
                    obs = presentation_observer_service.get_latest_observation(session_id)
                else:
                    async with lock:
                        now = time.time()
                        if now - self._last_obs_time.get(session_id, 0.0) < 2.5:
                            obs = presentation_observer_service.get_latest_observation(session_id)
                        else:
                            obs = await presentation_observer_service.run_observation_cycle(session_id)
                            self._last_obs_time[session_id] = time.time()
            else:
                obs = presentation_observer_service.get_latest_observation(session_id)

            if obs:
                presentation_detected = (
                    obs.presentation_state in [
                        PresentationMode.POWERPOINT_SHARED,
                        PresentationMode.SCREEN_SHARING,
                        "POWERPOINT_SHARED",
                        "SCREEN_SHARING"
                    ]
                )
            else:
                presentation_detected = False

            # Check coordinator cached flag ONLY if actively presenting
            if not presentation_detected and session_id in runtime_service._coordinators:
                coord = runtime_service._coordinators[session_id]
                if getattr(coord, "presentation_detected", False) and getattr(coord.session_manager, "state", None) == RuntimeState.PRESENTING:
                    presentation_detected = True
        except Exception as e:
            logger.error(f"MeetingStatusService | Failed to read presentation observer: {e}")
            presentation_detected = False

        # --------------------------------------------------------------------
        # 3. Evaluate Narration Audio Readiness
        # --------------------------------------------------------------------
        try:
            audio_ctrl = get_audio_controller(session_id)
            audio_ready = audio_ctrl.audio_ready()
        except Exception as e:
            logger.error(f"MeetingStatusService | Failed to check audio controller: {e}")
            audio_ready = False

        # --------------------------------------------------------------------
        # 4. Evaluate Runtime Package Assets
        # --------------------------------------------------------------------
        try:
            session_dir = storage_service.get_session_dir(session_id)
            has_manifest = (session_dir / "manifest.json").exists()
            has_timeline = (session_dir / "presentation_timeline.json").exists()
            slides_dir = session_dir / "slides"
            has_slides = slides_dir.exists() and len(
                list(slides_dir.glob("*.png")) + list(slides_dir.glob("*.jpg"))
            ) > 0

            status_ready = False
            if db:
                sess_rec = db.query(DBSessionModel).filter(DBSessionModel.id == session_id).first()
                status_ready = sess_rec.status in ["READY", "COMPLETED"] if sess_rec else False

            runtime_assets_ready = has_manifest or (has_slides and has_timeline) or status_ready
        except Exception as e:
            logger.error(f"MeetingStatusService | Failed to check runtime assets: {e}")
            runtime_assets_ready = False

        # --------------------------------------------------------------------
        # 5. Presentation Controller Overrides (Legacy / In-Progress Presentation)
        # --------------------------------------------------------------------
        from app.modules.presentation.presentation_runtime_controller import get_active_presentation_controller
        active_pres = get_active_presentation_controller(session_id)

        narration_state = "idle"
        if active_pres:
            if getattr(active_pres, "presentation_state", "") == "SLIDESHOW_RUNNING" and getattr(active_pres, "share_successful", False):
                presentation_detected = True
            audio_ready = True
            runtime_assets_ready = True
            meeting_connected = True
            if active_pres._is_paused:
                narration_state = "paused"
            elif active_pres.presentation_state in ["SLIDESHOW_RUNNING", "READY", "EDITOR_OPEN"]:
                narration_state = "presenting"
            elif active_pres.presentation_state == "FINISHED":
                narration_state = "finished_closing"
        elif session_id in runtime_service._coordinators:
            coord = runtime_service._coordinators[session_id]
            narration_state = getattr(coord, "narration_state", "idle")

        # Slide index and confidence from PresentationObserver
        current_slide = 0
        confidence = 0.0
        from app.modules.presentation_observer.observer.presentation_observer import presentation_observer
        if presentation_observer.context.prev_snapshot:
            current_slide = presentation_observer.current_slide()
            confidence = presentation_observer.confidence()

        # --------------------------------------------------------------------
        # 6. Authoritative Readiness Computation & Checklist Construction
        # --------------------------------------------------------------------
        ready_to_initiate = bool(meeting_connected)
        overall_ready = bool(
            meeting_connected and
            presentation_detected
        )
        bot_ready = ready_to_initiate

        blocked_reasons: List[str] = []
        if not meeting_connected:
            blocked_reasons.append("Waiting for bot to connect to Microsoft Teams meeting.")
        if not presentation_detected:
            blocked_reasons.append("PowerPoint presentation not yet shared in Teams (will attempt auto-open on Start).")

        reason = blocked_reasons[0] if blocked_reasons else None

        checklist = {
            "teams": {
                "status": "CONNECTED" if meeting_connected else "DISCONNECTED",
                "label": "Teams Meeting",
                "ok": meeting_connected,
                "action": "Bot connected to call" if meeting_connected else "Connect bot to Microsoft Teams call"
            },
            "presentation": {
                "status": "DETECTED" if presentation_detected else "WAITING FOR SHARE",
                "label": "Presentation Screen",
                "ok": presentation_detected,
                "action": "Presentation screen active and synchronized" if presentation_detected else "Click Start Induction to launch slideshow and share"
            },
            "audio": {
                "status": "READY" if audio_ready else "PENDING",
                "label": "Narration Audio",
                "ok": audio_ready,
                "action": "Audio tracks verified and loaded" if audio_ready else "Generate speech audio in Step 3"
            },
            "assets": {
                "status": "READY" if runtime_assets_ready else "MISSING",
                "label": "Runtime Assets",
                "ok": runtime_assets_ready,
                "action": "Manifest and slide assets verified" if runtime_assets_ready else "Prepare runtime package in Step 4"
            },
            "overall": {
                "status": "READY TO START" if meeting_connected else "BLOCKED",
                "label": "Overall Readiness",
                "ok": meeting_connected,
                "action": "Ready to launch PowerPoint slideshow and start induction." if meeting_connected else (blocked_reasons[0] if blocked_reasons else "Prerequisites incomplete")
            }
        }

        result = {
            "bot_ready": bot_ready,
            "overall_ready": overall_ready,
            "ready_to_initiate": ready_to_initiate,
            "meeting_connected": meeting_connected,
            "presentation_detected": presentation_detected,
            "audio_ready": audio_ready,
            "runtime_assets_ready": runtime_assets_ready,
            "participants": participants,
            "required_participants": required_participants,
            "participant_ready": participant_ready,
            "reason": reason,
            "blocked_reasons": blocked_reasons,
            "narration_state": narration_state,
            "current_slide": current_slide,
            "confidence": confidence,
            "checklist": checklist
        }

        logger.debug(f"MeetingStatusService | Final evaluation: bot_ready={bot_ready}, blocked={blocked_reasons}")
        return result

meeting_status_service = MeetingStatusService()
