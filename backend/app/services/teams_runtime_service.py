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
        from app.services.runtime_service import runtime_service
        coordinator = runtime_service.get_coordinator(db, session_id)
        current_state = coordinator.session_manager.state.value
        current_slide = coordinator.memory.current_slide_number
        
        return {
            "status": current_state,
            "current_slide": current_slide,
            "total_slides": len(coordinator.script_slides),
            "browser_connected": coordinator._browser_manager is not None,
            "meeting_connected": current_state == "CONNECTED"
        }

    async def prepare_runtime(self, db: DBSession, session_id: str) -> bool:
        from app.services.runtime_service import runtime_service
        coordinator = runtime_service.get_coordinator(db, session_id)
        return await coordinator.prepare_runtime()

    async def start_induction(self, db: DBSession, session_id: str) -> bool:
        from app.services.runtime_service import runtime_service
        coordinator = runtime_service.get_coordinator(db, session_id)
        return await coordinator.start_induction()

    async def join_meeting(self, db: DBSession, session_id: str, meeting_url: str) -> bool:
        from app.services.runtime_service import runtime_service
        coordinator = runtime_service.get_coordinator(db, session_id)
        return await coordinator.join_meeting(meeting_url)

    async def finish_runtime(self, db: DBSession, session_id: str) -> bool:
        from app.services.runtime_service import runtime_service
        coordinator = runtime_service.get_coordinator(db, session_id)
        return await coordinator.finish_presentation()

teams_runtime_service = TeamsRuntimeService()
