from sqlalchemy.orm import Session as DBSession
from app.modules.meeting_bot.services.meeting_bot_service import meeting_bot_service
from app.modules.meeting_bot.teams.participant_monitor import participant_monitor
from app.modules.meeting_bot.media.audio_controller import get_audio_controller
from app.modules.presentation_observer.services.presentation_observer_service import presentation_observer_service
from app.services.runtime_service import runtime_service
from loguru import logger

class MeetingStatusService:
    async def evaluate_status(self, db: DBSession, session_id: str) -> dict:
        """
        Aggregates live meeting state and computes readiness for HR authorization.
        """
        bot = meeting_bot_service.get_bot(session_id)
        logger.info(f"MeetingStatusService | session_id: {session_id} | bot exists: {bot is not None} | page exists: {bot.context.page is not None if bot else False}")
        
        meeting_connected = False
        participants = 0
        presentation_detected = False
        audio_ready = False
        
        # 1. Evaluate connection and participant metrics
        raw_participants = []
        if bot and bot.context.page:
            try:
                meeting_connected = await participant_monitor.meeting_active(bot.context.page)
                if meeting_connected:
                    raw_participants = await participant_monitor.get_participants(bot.context)
            except Exception as e:
                logger.error(f"MeetingStatusService | Failed to read Teams metrics: {e}")

        # 2. Retrieve expected participant count from Session context
        required_participants = 1
        try:
            ctx = runtime_service.get_runtime_context(db, session_id)
            required_participants = len(ctx.get("employees", []))
        except Exception as e:
            logger.debug(f"MeetingStatusService | Using default required count due to context lookup: {e}")

        # Exclude only the bot from headcount
        filtered_participants = []
        for p in raw_participants:
            p_lower = p.lower().strip()
            # Skip bot
            if "kone ai" in p_lower or "bot" in p_lower:
                continue
            filtered_participants.append(p)

        participants = len(filtered_participants)

        # 3. Evaluate presentation status
        try:
            from app.modules.presentation_observer.services.presentation_observer_service import presentation_observer_service
            from app.modules.semantic_browser.models.presentation_state import PresentationMode
            if bot and bot.context.page:
                obs = await presentation_observer_service.run_observation_cycle(session_id)
                if obs:
                    presentation_detected = obs.presentation_state in [
                        PresentationMode.POWERPOINT_SHARED,
                        PresentationMode.SCREEN_SHARING
                    ]
            else:
                presentation_detected = False
        except Exception as e:
            logger.error(f"MeetingStatusService | Failed to read presentation observer: {e}")

        # 4. Evaluate audio loaded status
        try:
            audio_ctrl = get_audio_controller(session_id)
            audio_ready = audio_ctrl.audio_ready()
        except Exception as e:
            logger.error(f"MeetingStatusService | Failed to check audio controller: {e}")

        # 5. Compute ready status and reason
        bot_ready = meeting_connected and presentation_detected and audio_ready
        
        reason = None
        if not meeting_connected:
            reason = "Waiting for bot to connect to meeting"
        elif not presentation_detected:
            reason = "Waiting for presentation to be shared"
        elif not audio_ready:
            reason = "Audio narration assets not fully prepared or loaded"

        # 6. Retrieve active narration state if coordinator active
        from app.services.runtime_service import runtime_service
        narration_state = "idle"
        if session_id in runtime_service._coordinators:
            narration_state = runtime_service._coordinators[session_id].narration_state

        # 7. Retrieve slide index and confidence from PresentationObserver
        current_slide = 0
        confidence = 0.0
        from app.modules.presentation_observer.observer.presentation_observer import presentation_observer
        if presentation_observer.context.prev_snapshot:
            current_slide = presentation_observer.current_slide()
            confidence = presentation_observer.confidence()

        result = {
            "participants": participants,
            "required_participants": required_participants,
            "presentation_detected": presentation_detected,
            "audio_ready": audio_ready,
            "meeting_connected": meeting_connected,
            "bot_ready": bot_ready,
            "reason": reason,
            "narration_state": narration_state,
            "current_slide": current_slide,
            "confidence": confidence
        }
        
        logger.debug(f"MeetingStatusService | Evaluation result: {result}")
        return result

meeting_status_service = MeetingStatusService()
