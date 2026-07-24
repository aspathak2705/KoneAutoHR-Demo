import asyncio
import datetime
from sqlalchemy.orm import Session as DBSession
from app.db.database import SessionLocal
from app.models.runtime import Runtime
from app.models.meeting import Meeting
from app.models.session import Session
from app.services.event_bus import runtime_event_bus
from app.services.teams_runtime_service import teams_runtime_service
from loguru import logger

class RuntimeSchedulerService:
    """
    Sprint RC-1 — Runtime Scheduler (Production Hardened)
    Automatically schedules, monitors, and recovers meeting runtimes.
    """
    def __init__(self):
        self._scheduled_sessions = set()
        self._launch_locks = set()

    def schedule_session(self, db: DBSession, session_id: str) -> dict:
        """
        POST /runtime/{session_id}/schedule
        Reads meeting date/time and marks runtime state as SCHEDULED -> WAITING_FOR_TIME.
        """
        session = db.query(Session).filter(Session.id == session_id).first()
        if not session:
            raise ValueError(f"Session {session_id} not found.")

        meeting = db.query(Meeting).filter(Meeting.session_id == session_id).first()
        if not meeting or not meeting.date or not meeting.time:
            raise ValueError(f"Session {session_id} is missing meeting date/time configuration.")

        runtime = db.query(Runtime).filter(Runtime.session_id == session_id).first()
        if not runtime:
            runtime = Runtime(session_id=session_id)
            db.add(runtime)

        runtime.state = "SCHEDULED"
        runtime.current_step = "WAITING_FOR_TIME"
        runtime.meeting_status = "SCHEDULED"
        runtime.last_heartbeat = datetime.datetime.now()
        runtime.last_error = None
        db.commit()

        self._scheduled_sessions.add(session_id)
        logger.info(f"[Scheduler] Meeting scheduled for session {session_id} at {meeting.date} {meeting.time}")
        runtime_event_bus.publish(session_id, "MeetingScheduled", {"session_id": session_id, "date": meeting.date, "time": meeting.time})

        return self.get_schedule_status(db, session_id)

    def handle_meeting_time_update(self, db: DBSession, session_id: str) -> None:
        """
        Edge Case 4: HR Edits Meeting Time.
        Resets scheduler timer and returns state to SCHEDULED.
        """
        runtime = db.query(Runtime).filter(Runtime.session_id == session_id).first()
        if runtime and runtime.state not in ["CONNECTED", "COMPLETED"]:
            runtime.state = "SCHEDULED"
            runtime.current_step = "WAITING_FOR_TIME"
            runtime.last_error = None
            runtime.last_heartbeat = datetime.datetime.now()
            db.commit()
            self._scheduled_sessions.add(session_id)
            logger.info(f"[Scheduler] HR updated meeting time for session {session_id}. Reset schedule timer.")

    def get_schedule_status(self, db: DBSession, session_id: str) -> dict:
        """
        GET /runtime/{session_id}/schedule
        """
        session = db.query(Session).filter(Session.id == session_id).first()
        meeting = db.query(Meeting).filter(Meeting.session_id == session_id).first() if session else None
        runtime = db.query(Runtime).filter(Runtime.session_id == session_id).first()

        state = runtime.state if runtime else "IDLE"
        scheduled_time = None
        if meeting and meeting.date and meeting.time:
            scheduled_time = f"{meeting.date} {meeting.time}"

        return {
            "session_id": session_id,
            "state": state,
            "scheduled_time": scheduled_time,
            "meeting_url": meeting.teams_url if meeting else None,
            "is_scheduled": state in ["SCHEDULED", "WAITING_FOR_TIME", "LAUNCHING", "JOINING", "CONNECTED", "WAITING"],
            "last_heartbeat": runtime.last_heartbeat.isoformat() if runtime and runtime.last_heartbeat else None,
            "last_error": runtime.last_error if runtime else None
        }

    def trigger_launch_if_due(self, db: DBSession, session_id: str) -> bool:
        """
        Checks system time vs meeting schedule and triggers launch.
        Handles Edge Cases:
        - Already connected/launching (Edge Case 5)
        - Mutex lock prevention (Edge Case 3)
        - Past expiration window (Edge Case 2)
        """
        # Edge Case 3 & 5: Already connected, launching, or currently locked
        if session_id in self._launch_locks:
            return False

        runtime = db.query(Runtime).filter(Runtime.session_id == session_id).first()
        if not runtime or runtime.state in ["LAUNCHING", "JOINING", "CONNECTED", "WAITING", "COMPLETED", "EXPIRED"]:
            return False

        meeting = db.query(Meeting).filter(Meeting.session_id == session_id).first()
        if not meeting or not meeting.date or not meeting.time:
            return False

        now = datetime.datetime.now()
        try:
            scheduled_dt = datetime.datetime.strptime(f"{meeting.date} {meeting.time}", "%Y-%m-%d %H:%M")
        except Exception:
            scheduled_dt = now

        # Edge Case 2: What if meeting time has already passed (> 30 mins ago)?
        time_diff_minutes = (now - scheduled_dt).total_seconds() / 60.0

        if time_diff_minutes > 30:
            logger.warning(f"[Scheduler] Session {session_id} meeting schedule window expired ({time_diff_minutes:.1f} mins past).")
            runtime.state = "EXPIRED"
            runtime.last_error = f"Schedule expired ({meeting.date} {meeting.time} was > 30 minutes ago)."
            db.commit()
            return False

        # Lock session launch
        self._launch_locks.add(session_id)
        try:
            if now >= scheduled_dt or runtime.state in ["SCHEDULED", "WAITING_FOR_TIME"]:
                logger.info(f"[Scheduler] Triggering autonomous launch for session {session_id}...")
                teams_runtime_service.launch_session(session_id)
                teams_runtime_service.join_meeting(session_id)
                return True
        finally:
            self._launch_locks.discard(session_id)

        return False

    def poll_scheduled_launches(self, db: DBSession) -> int:
        """
        Periodic background worker scan (runs every 5s).
        Scans ONLY scheduled sessions and triggers launch if time has arrived.
        NEVER re-triggers already active/connected sessions.
        """
        runtimes = db.query(Runtime).filter(
            Runtime.state.in_(["SCHEDULED", "WAITING_FOR_TIME"])
        ).all()
        launched_count = 0
        for rt in runtimes:
            if self.trigger_launch_if_due(db, rt.session_id):
                launched_count += 1
        return launched_count

    def startup_recovery(self, db: DBSession) -> dict:
        """
        Executed ONCE during FastAPI lifespan startup to clean up leftover runtime states after a server restart.
        Does NOT automatically spawn browser windows on server startup.
        Browser launch occurs ONLY when HR clicks 'Start Induction' or scheduled meeting time arrives.
        """
        runtimes = db.query(Runtime).filter(
            Runtime.state.in_(["SCHEDULED", "WAITING_FOR_TIME", "LAUNCHING", "JOINING", "CONNECTED", "WAITING", "RECONNECTING"])
        ).all()

        recovered = {"rescheduled": 0, "reset": 0, "expired": 0}

        for rt in runtimes:
            if rt.state in ["SCHEDULED", "WAITING_FOR_TIME"]:
                self._scheduled_sessions.add(rt.session_id)
                recovered["rescheduled"] += 1
            elif rt.state in ["CONNECTED", "WAITING", "JOINING", "LAUNCHING", "RECONNECTING"]:
                logger.info(f"[RuntimeRecovery] Resetting stale session {rt.session_id} state from {rt.state} -> PREPARING on server startup.")
                rt.state = "PREPARING"
                rt.last_error = None
                db.commit()
                recovered["reset"] += 1
                try:
                    from app.core.cleanup_manager import cleanup_manager
                    try:
                        loop = asyncio.get_running_loop()
                        loop.create_task(cleanup_manager.cleanup_session(rt.session_id))
                    except RuntimeError:
                        # Fallback for no running event loop
                        asyncio.run(cleanup_manager.cleanup_session(rt.session_id))
                except Exception as ex:
                    logger.error(f"[RuntimeRecovery] Failed to trigger cleanup for stale session {rt.session_id}: {ex}")

        if any(recovered.values()):
            logger.info(f"[RuntimeRecovery] Startup recovery completed: {recovered}")
        return recovered

runtime_scheduler_service = RuntimeSchedulerService()
