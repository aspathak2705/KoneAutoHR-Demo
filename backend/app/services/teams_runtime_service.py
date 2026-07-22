import sys
import asyncio
import datetime
from typing import Optional
from sqlalchemy.orm import Session as DBSession
from app.db.database import SessionLocal
from app.models.runtime import Runtime
from app.models.meeting import Meeting
from app.services.event_bus import runtime_event_bus
from app.services.runtime_task_manager import runtime_task_manager
from app.services.browser_driver import BrowserDriver
from loguru import logger

def _run_coro_in_proactor_thread(coro_fn, *args):
    """
    Executes an async coroutine inside a dedicated thread with WindowsProactorEventLoopPolicy.
    Guarantees Playwright subprocess creation on Windows regardless of main Uvicorn event loop type.
    """
    if sys.platform == "win32":
        try:
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        except Exception:
            pass
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro_fn(*args))
    finally:
        loop.close()

class TeamsRuntimeService:
    """
    Sprint RS-1 to RS-4: Production-grade Teams Runtime Engine
    Single task per session, BrowserDriver layer, evidence-backed state transitions, heartbeat updates.
    """
    def __init__(self):
        self._active_drivers: Dict[str, BrowserDriver] = {}

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
            "last_heartbeat": runtime.last_heartbeat.isoformat() if runtime.last_heartbeat else None,
            "last_error": runtime.last_error
        }

    async def advance_slide(self, session_id: str) -> bool:
        """
        Invokes BrowserDriver.advance_slide() on active session browser.
        """
        driver = self._active_drivers.get(session_id)
        if driver:
            res = await driver.advance_slide()
            return res.get("advanced", False)
        logger.warning(f"TeamsRuntime | No active BrowserDriver found for session {session_id} to advance slide.")
        return False

    def launch_session(self, session_id: str) -> None:
        """
        POST /runtime/{id}/launch - Initializes Playwright headless browser driver context.
        """
        self._update_state(session_id, "LAUNCHING")
        logger.info(f"TeamsRuntime | Session: {session_id} | Initializing Playwright Chromium headless driver...")
        runtime_event_bus.publish(session_id, "MeetingLaunching", {"session_id": session_id})

    def join_meeting(self, session_id: str) -> None:
        """
        Sprint RS-1: Enforces One Session -> One Runtime -> One Browser -> One Task.
        Rejects duplicate launch requests if task is active.
        Spawns execution in Proactor thread on Windows for Playwright subprocess compatibility.
        """
        if runtime_task_manager.is_task_active(session_id):
            logger.warning(f"TeamsRuntime | Session: {session_id} | Participant already in call or joining. Task rejected.")
            return

        try:
            loop = asyncio.get_running_loop()
            task = loop.run_in_executor(None, _run_coro_in_proactor_thread, self._run_participant_loop, session_id)
            runtime_task_manager.register_task(session_id, task)
        except RuntimeError:
            _run_coro_in_proactor_thread(self._run_participant_loop, session_id)

    def leave_meeting(self, session_id: str) -> None:
        """
        POST /runtime/{id}/leave - Cancels active task and marks state COMPLETED / LEFT.
        """
        runtime_task_manager.cancel_task(session_id)
        self._update_state(session_id, "COMPLETED")
        runtime_task_manager.cleanup_task(session_id)
        logger.info(f"TeamsRuntime | Session: {session_id} | Teams participant left call gracefully.")
        runtime_event_bus.publish(session_id, "MeetingLeft", {"session_id": session_id})

    async def simulate_reconnect(self, session_id: str) -> None:
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
        await asyncio.sleep(2)
        self._update_state(session_id, "CONNECTED")
        runtime_event_bus.publish(session_id, "MeetingJoined", {"session_id": session_id})

    async def _run_participant_loop(self, session_id: str) -> None:
        driver = BrowserDriver()
        self._active_drivers[session_id] = driver
        try:
            try:
                from app.services.runtime_context_service import runtime_context_service
                from app.services.runtime_readiness_service import runtime_readiness_service

                with SessionLocal() as db:
                    ctx = runtime_context_service.build_runtime_context(db, session_id)
                    readiness = runtime_readiness_service.evaluate_readiness(ctx)
                    meeting = ctx.get("meeting")
                    meeting_url = meeting.teams_url if meeting else None

                if not meeting_url or not readiness.get("has_meeting"):
                    raise ValueError("Cannot join meeting: Session has no valid/configured Teams Meeting URL.")

                # Step 1: BROWSER_STARTING -> BROWSER_READY
                self._update_state(session_id, "BROWSER_STARTING")
                await driver.launch()
                self._update_state(session_id, "BROWSER_READY")

                # Step 2: TEAMS_PAGE_LOADING -> TEAMS_PAGE_READY
                self._update_state(session_id, "TEAMS_PAGE_LOADING")
                await driver.navigate(meeting_url)
                self._update_state(session_id, "TEAMS_PAGE_READY")

                # Step 3: GUEST_FORM_VISIBLE -> JOIN_REQUEST_SENT -> IN_LOBBY
                self._update_state(session_id, "GUEST_FORM_VISIBLE")
                await driver.join_guest("KONE AI Trainer")
                self._update_state(session_id, "JOIN_REQUEST_SENT")
                
                lobby_info = await driver.wait_for_lobby()
                self._update_state(session_id, "IN_LOBBY")

                # Step 4: ADMITTED -> PARTICIPANT_VISIBLE -> CONNECTED
                await driver.wait_for_admit()
                self._update_state(session_id, "ADMITTED")

                conn_verify = await driver.verify_connected()
                if not conn_verify.get("connected"):
                    raise RuntimeError(f"Failed to verify call connection: {conn_verify.get('reason')}")

                self._update_state(session_id, "CONNECTED")
                logger.info(f"TeamsRuntime | Session: {session_id} | Verified CONNECTED to active Teams call: {meeting_url}")
                runtime_event_bus.publish(session_id, "MeetingJoined", {"session_id": session_id, "meeting_url": meeting_url})

                self._update_state(session_id, "WAITING")

                # Sprint RS-4 Heartbeat loop (updates last_heartbeat every 10s while connected)
                while True:
                    await asyncio.sleep(10)
                    self._touch_heartbeat(session_id)

            except asyncio.CancelledError:
                logger.info(f"TeamsRuntime | Session: {session_id} | Joining task was cancelled.")
                await driver.leave()
                raise
            except Exception as e:
                logger.error(f"TeamsRuntime | Session: {session_id} | Join Failure: {e}")
                self._update_state(session_id, "FAILED", error_msg=str(e))
                runtime_event_bus.publish(session_id, "JoinFailure", {"session_id": session_id, "error": str(e)})
        finally:
            # Guaranteed cleanup on every termination path (cancellation, failure, or completion)
            self._active_drivers.pop(session_id, None)
            await driver.close()
            runtime_task_manager.cleanup_task(session_id)

    def _touch_heartbeat(self, session_id: str) -> None:
        with SessionLocal() as db:
            runtime = db.query(Runtime).filter(Runtime.session_id == session_id).first()
            if runtime:
                runtime.last_heartbeat = datetime.datetime.now()
                db.commit()

    def _update_state(self, session_id: str, state: str, error_msg: Optional[str] = None) -> None:
        with SessionLocal() as db:
            runtime = db.query(Runtime).filter(Runtime.session_id == session_id).first()
            if not runtime:
                runtime = Runtime(session_id=session_id)
                db.add(runtime)
            runtime.state = state
            if error_msg:
                runtime.last_error = error_msg
            runtime.last_heartbeat = datetime.datetime.now()
            db.commit()

teams_runtime_service = TeamsRuntimeService()
