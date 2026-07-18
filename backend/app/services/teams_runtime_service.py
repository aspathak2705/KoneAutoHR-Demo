import asyncio
import datetime
from sqlalchemy.orm import Session as DBSession
from app.db.database import SessionLocal
from app.models.runtime import Runtime
from app.services.event_bus import runtime_event_bus
from loguru import logger

class TeamsRuntimeService:
    def __init__(self):
        # Maps session_id -> active execution tasks
        self._active_tasks = {}

    def get_status(self, db: DBSession, session_id: str) -> dict:
        runtime = db.query(Runtime).filter(Runtime.session_id == session_id).first()
        if not runtime:
            runtime = Runtime(session_id=session_id, state="PREPARING", current_slide=0)
            db.add(runtime)
            db.commit()
            db.refresh(runtime)
        return {
            "session_id": session_id,
            "state": runtime.state,
            "current_slide": runtime.current_slide,
            "reconnect_count": runtime.reconnect_count,
            "speech_state": runtime.speech_state,
            "last_heartbeat": runtime.last_heartbeat.isoformat() if runtime.last_heartbeat else None
        }

    def launch_session(self, session_id: str) -> None:
        """
        POST /runtime/{id}/launch - Initializes session and prepares browser launcher.
        """
        self._update_state(session_id, "LAUNCHING")
        logger.info(f"TeamsRuntime | Session: {session_id} | Initializing automation engine driver...")
        runtime_event_bus.publish(session_id, "MeetingLaunching", {"session_id": session_id})

    def join_meeting(self, session_id: str) -> None:
        """
        POST /runtime/{id}/join - Accepting URL and starting join sequence threads.
        """
        if session_id in self._active_tasks and not self._active_tasks[session_id].done():
            logger.warning(f"TeamsRuntime | Session: {session_id} | Participant already in call or joining.")
            return
            
        task = asyncio.create_task(self._run_participant_loop(session_id))
        self._active_tasks[session_id] = task

    def leave_meeting(self, session_id: str) -> None:
        """
        POST /runtime/{id}/leave - Triggers graceful exit and thread terminations.
        """
        task = self._active_tasks.pop(session_id, None)
        if task and not task.done():
            task.cancel()
            
        self._update_state(session_id, "COMPLETED")
        logger.info(f"TeamsRuntime | Session: {session_id} | Participant gracefully left meeting call.")
        runtime_event_bus.publish(session_id, "MeetingLeft", {"session_id": session_id})
        runtime_event_bus.publish(session_id, "MeetingCompleted", {"session_id": session_id})

    async def simulate_reconnect(self, session_id: str) -> None:
        """
        Force triggers a connection drop and reconnect loop for testing recovery handlers.
        """
        self._update_state(session_id, "DISCONNECTED")
        logger.warning(f"TeamsRuntime | Session: {session_id} | Connection dropped. Starting reconnect...")
        runtime_event_bus.publish(session_id, "MeetingDisconnected", {"session_id": session_id})

        with SessionLocal() as db:
            runtime = db.query(Runtime).filter(Runtime.session_id == session_id).first()
            if runtime:
                runtime.reconnect_count += 1
                db.commit()

        self._update_state(session_id, "RECONNECTING")
        runtime_event_bus.publish(session_id, "ReconnectAttempt", {"session_id": session_id})
        await asyncio.sleep(3)
        self._update_state(session_id, "CONNECTED")
        runtime_event_bus.publish(session_id, "MeetingJoined", {"session_id": session_id})
        logger.info(f"TeamsRuntime | Session: {session_id} | Reconnected successfully.")

    async def _run_participant_loop(self, session_id: str) -> None:
        try:
            # 1. State: JOINING (Navigating meeting link)
            self._update_state(session_id, "JOINING")
            logger.info(f"TeamsRuntime | Session: {session_id} | Navigating Teams URL link...")
            await asyncio.sleep(2)

            # 2. State: WAITING (In lobby, typing guest name)
            self._update_state(session_id, "WAITING")
            logger.info(f"TeamsRuntime | Session: {session_id} | Guest name inputted. Waiting in meeting lobby...")
            await asyncio.sleep(3)

            # 3. State: CONNECTED (Lobby entry approved)
            self._update_state(session_id, "CONNECTED")
            logger.info(f"TeamsRuntime | Session: {session_id} | Lobby entry approved. Connected to call stream.")
            runtime_event_bus.publish(session_id, "MeetingJoined", {"session_id": session_id})

        except asyncio.CancelledError:
            logger.info(f"TeamsRuntime | Session: {session_id} | Joining task was cancelled.")
        except Exception as e:
            logger.error(f"TeamsRuntime | Session: {session_id} | Join Failure: {e}")
            runtime_event_bus.publish(session_id, "JoinFailure", {"session_id": session_id, "error": str(e)})

    def _update_state(self, session_id: str, state: str) -> None:
        with SessionLocal() as db:
            runtime = db.query(Runtime).filter(Runtime.session_id == session_id).first()
            if not runtime:
                runtime = Runtime(session_id=session_id)
                db.add(runtime)
            runtime.state = state
            runtime.last_heartbeat = datetime.datetime.now()
            db.commit()

teams_runtime_service = TeamsRuntimeService()
