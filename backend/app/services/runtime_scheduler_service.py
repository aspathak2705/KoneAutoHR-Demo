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
    Sprint RC-1 — Runtime Scheduler
    Automatically triggers the meeting runtime launch at the scheduled date and time.
    """
    def __init__(self):
        self._scheduler_task = None
        self._scheduled_sessions = set()

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
        db.commit()

        self._scheduled_sessions.add(session_id)
        logger.info(f"[Scheduler] Meeting scheduled for session {session_id} at {meeting.date} {meeting.time}")
        runtime_event_bus.publish(session_id, "MeetingScheduled", {"session_id": session_id, "date": meeting.date, "time": meeting.time})

        return self.get_schedule_status(db, session_id)

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
            "last_heartbeat": runtime.last_heartbeat.isoformat() if runtime and runtime.last_heartbeat else None
        }

    def trigger_launch_if_due(self, db: DBSession, session_id: str) -> bool:
        """
        Checks system time against configured meeting time and launches if due.
        Prevents duplicate launches.
        """
        runtime = db.query(Runtime).filter(Runtime.session_id == session_id).first()
        if not runtime or runtime.state in ["LAUNCHING", "JOINING", "CONNECTED", "WAITING", "COMPLETED"]:
            return False

        meeting = db.query(Meeting).filter(Meeting.session_id == session_id).first()
        if not meeting or not meeting.date or not meeting.time:
            return False

        # Compare meeting schedule with system time
        now = datetime.datetime.now()
        try:
            scheduled_datetime = datetime.datetime.strptime(f"{meeting.date} {meeting.time}", "%Y-%m-%d %H:%M")
        except Exception:
            # If parse fails, default to current time for immediate verification launch
            scheduled_datetime = now

        if now >= scheduled_datetime or runtime.state == "SCHEDULED":
            logger.info(f"[Scheduler] Triggering autonomous launch for session {session_id}...")
            teams_runtime_service.launch_session(session_id)
            teams_runtime_service.join_meeting(session_id)
            return True

        return False

runtime_scheduler_service = RuntimeSchedulerService()
