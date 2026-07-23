import logging
from sqlalchemy.orm import Session as DBSession

logger = logging.getLogger("app.services.teams_runtime")

class TeamsRuntimeService:
    """
    Mock Teams Runtime Service for local simulation loop.
    Controls session lifecycle and slide transitions without Microsoft Graph/Teams dependencies.
    """
    def get_status(self, db: DBSession, session_id: str):
        return {
            "status": "connected",
            "current_slide": 0,
            "total_slides": 5,
            "browser_connected": True,
            "meeting_connected": True
        }

    def launch_session(self, session_id: str):
        logger.info(f"Mock Teams Runtime | Launched browser runtime for session: {session_id}")

    def join_meeting(self, session_id: str):
        logger.info(f"Mock Teams Runtime | Connected browser to simulated meeting: {session_id}")

    def leave_meeting(self, session_id: str):
        logger.info(f"Mock Teams Runtime | Disconnected browser from simulated meeting: {session_id}")

    async def advance_slide(self, session_id: str) -> bool:
        logger.info(f"Mock Teams Runtime | Advanced presentation slide for session: {session_id}")
        return True

    async def simulate_reconnect(self, session_id: str):
        logger.info(f"Mock Teams Runtime | Reconnecting browser for session: {session_id}")
        return True

teams_runtime_service = TeamsRuntimeService()
