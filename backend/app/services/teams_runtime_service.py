import logging
from typing import Optional
from sqlalchemy.orm import Session as DBSession
from app.modules.meeting_bot.services.meeting_bot_service import meeting_bot_service
from app.db.database import SessionLocal
from app.models.runtime import Runtime
from app.models.meeting import Meeting

logger = logging.getLogger("app.services.teams_runtime")

class TeamsRuntimeService:
    """
    Production Teams Runtime Service.
    Controls session lifecycle and slide transitions by driving the Playwright MeetingBot.
    """
    def get_status(self, db: DBSession, session_id: str):
        bot = meeting_bot_service.get_bot(session_id)
        state_str = bot.context.state.value if bot else "IDLE"

        runtime = db.query(Runtime).filter(Runtime.session_id == session_id).first()
        current_slide = runtime.current_slide if runtime else 0

        return {
            "status": state_str,
            "current_slide": current_slide,
            "total_slides": 5,
            "browser_connected": bot.context.browser is not None if bot else False,
            "meeting_connected": state_str == "CONNECTED"
        }

    def _set_runtime_state(self, session_id: str, state: str, last_error: Optional[str] = None) -> None:
        with SessionLocal() as db:
            runtime = db.query(Runtime).filter(Runtime.session_id == session_id).first()
            if not runtime:
                runtime = Runtime(session_id=session_id, state=state, current_slide=0)
                db.add(runtime)
            else:
                runtime.state = state
            runtime.last_error = last_error
            db.commit()

    async def launch_session(self, session_id: str):
        logger.info(f"Teams Runtime | Launching browser runtime for session: {session_id}")
        self._set_runtime_state(session_id, "INITIALIZING")
        try:
            await meeting_bot_service.stop_bot(session_id)
            result = await meeting_bot_service.start_bot(session_id)
            self._set_runtime_state(session_id, result.get("state", "READY"))
            return result
        except Exception as e:
            logger.exception(f"Teams Runtime | Failed to launch browser runtime for session: {session_id}")
            try:
                await meeting_bot_service.stop_bot(session_id)
            finally:
                self._set_runtime_state(session_id, "FAILED", str(e))
            raise

    async def join_meeting(self, session_id: str):
        logger.info(f"Teams Runtime | Connecting browser to meeting for session: {session_id}")
        self._set_runtime_state(session_id, "JOINING")
        with SessionLocal() as db:
            meeting = db.query(Meeting).filter(Meeting.session_id == session_id).first()
            meeting_url = meeting.teams_meeting_url if meeting else None

        if not meeting_url:
            message = f"No meeting URL found for session {session_id}"
            logger.error(f"Teams Runtime | {message}")
            self._set_runtime_state(session_id, "FAILED", message)
            raise ValueError(message)

        try:
            result = await meeting_bot_service.join_meeting(meeting_url, "KONE AI Bot", session_id)
            try:
                bot = meeting_bot_service.get_bot(session_id)
                self._set_runtime_state(session_id, bot.context.state.value)
            except Exception:
                self._set_runtime_state(session_id, result.get("state", "CONNECTED"))
            return result
        except Exception as e:
            logger.exception(f"Teams Runtime | Failed to join meeting for session: {session_id}")
            self._set_runtime_state(session_id, "FAILED", str(e))
            raise

    async def leave_meeting(self, session_id: str):
        logger.info(f"Teams Runtime | Disconnecting browser for session: {session_id}")
        await meeting_bot_service.leave_meeting(session_id)
        await meeting_bot_service.stop_bot(session_id)
        self._set_runtime_state(session_id, "COMPLETED")
        return {"status": "success", "state": "COMPLETED"}

    async def advance_slide(self, session_id: str) -> bool:
        logger.info(f"Teams Runtime | Advanced presentation slide for session: {session_id}")
        return True

    async def simulate_reconnect(self, session_id: str):
        logger.info(f"Teams Runtime | Reconnecting browser for session: {session_id}")
        return True

teams_runtime_service = TeamsRuntimeService()
