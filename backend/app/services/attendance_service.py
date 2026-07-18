import datetime
from typing import Any
from sqlalchemy.orm import Session as DBSession
from app.db.database import SessionLocal
from app.models.attendance import Attendance
from app.models.session import Session
from app.modules.induction.employees.excel_parser import parse_employees_excel
from app.services.event_bus import runtime_event_bus
from loguru import logger

class AttendanceService:
    def __init__(self):
        # Subscribe to Event Bus topics
        runtime_event_bus.subscribe("MeetingJoined", self._on_meeting_joined)
        runtime_event_bus.subscribe("MeetingLeft", self._on_meeting_left)
        runtime_event_bus.subscribe("MeetingCompleted", self._on_meeting_completed)

    def get_attendance_log(self, db: DBSession, session_id: str) -> list[Attendance]:
        return db.query(Attendance).filter(Attendance.session_id == session_id).all()

    def get_attendance_summary(self, db: DBSession, session_id: str) -> dict:
        """
        Sprint RC-3: Compiles attendance logs and summaries.
        """
        logs = self.get_attendance_log(db, session_id)
        
        total_invited = 0
        session = db.query(Session).filter(Session.id == session_id).first()
        if session and session.employee_list:
            try:
                employees = parse_employees_excel(session.employee_list.storage_path)
                total_invited = len(employees)
            except Exception:
                pass

        joined_count = len(logs)
        completed_count = len([l for l in logs if l.status == "PRESENT"])
        absent_count = max(0, total_invited - joined_count)

        summary_list = []
        for log in logs:
            summary_list.append({
                "name": log.attendee_name,
                "email": log.attendee_email,
                "joined_at": log.joined_at.isoformat() if log.joined_at else None,
                "left_at": log.left_at.isoformat() if log.left_at else None,
                "duration_minutes": round(log.duration_seconds / 60, 1),
                "questions_asked": log.questions_asked,
                "status": log.status
            })

        participation_rate = (joined_count / total_invited * 100) if total_invited > 0 else 0.0

        return {
            "session_id": session_id,
            "total_invited": total_invited,
            "joined": joined_count,
            "completed_present": completed_count,
            "absent": absent_count,
            "participation_rate_percent": round(participation_rate, 1),
            "attendees": summary_list
        }

    def log_join(self, session_id: str, name: str, email: str) -> None:
        with SessionLocal() as db:
            log = db.query(Attendance).filter(
                Attendance.session_id == session_id,
                Attendance.attendee_email == email
            ).first()

            if not log:
                log = Attendance(
                    session_id=session_id,
                    attendee_name=name,
                    attendee_email=email,
                    joined_at=datetime.datetime.now(),
                    status="PRESENT" # Default to PRESENT upon join
                )
                db.add(log)
            else:
                log.joined_at = datetime.datetime.now()
                log.status = "PRESENT"
            db.commit()

    def log_leave(self, session_id: str, email: str) -> None:
        with SessionLocal() as db:
            log = db.query(Attendance).filter(
                Attendance.session_id == session_id,
                Attendance.attendee_email == email
            ).first()

            if log and log.joined_at:
                log.left_at = datetime.datetime.now()
                delta = log.left_at - log.joined_at
                log.duration_seconds = int(delta.total_seconds())

                # Attendance Status categorization rules:
                # If attendee spends less than 1 minute -> flag PARTIAL
                if log.duration_seconds < 60:
                    log.status = "PARTIAL"
                # If attendee leaves early (less than 20 minutes) -> flag LEFT_EARLY
                elif log.duration_seconds < 1200:
                    log.status = "LEFT_EARLY"
                else:
                    log.status = "PRESENT"

                db.commit()

    def increment_questions(self, session_id: str, email: str) -> None:
        with SessionLocal() as db:
            log = db.query(Attendance).filter(
                Attendance.session_id == session_id,
                Attendance.attendee_email == email
            ).first()
            if log:
                log.questions_asked += 1
                db.commit()

    # Event Bus Subscription Callbacks
    def _on_meeting_joined(self, session_id: str, data: Any) -> None:
        logger.info(f"AttendanceService | Event 'MeetingJoined' received for session {session_id}")
        # Auto-seed mock attendees joining session
        with SessionLocal() as db:
            session = db.query(Session).filter(Session.id == session_id).first()
            if session and session.employee_list:
                try:
                    employees = parse_employees_excel(session.employee_list.storage_path)
                    for emp in employees:
                        self.log_join(session_id, emp.get("name", "New Employee"), emp.get("email", "new@kone.com"))
                except Exception as e:
                    logger.error(f"AttendanceService | Failed auto-join logs: {e}")

    def _on_meeting_left(self, session_id: str, data: Any) -> None:
        logger.info(f"AttendanceService | Event 'MeetingLeft' received for session {session_id}")
        with SessionLocal() as db:
            logs = db.query(Attendance).filter(Attendance.session_id == session_id).all()
            for log in logs:
                self.log_leave(session_id, log.attendee_email)

    def _on_meeting_completed(self, session_id: str, data: Any) -> None:
        logger.info(f"AttendanceService | Event 'MeetingCompleted' received for session {session_id}")
        with SessionLocal() as db:
            logs = db.query(Attendance).filter(Attendance.session_id == session_id).all()
            for log in logs:
                if not log.left_at:
                    self.log_leave(session_id, log.attendee_email)
attendance_service = AttendanceService()
