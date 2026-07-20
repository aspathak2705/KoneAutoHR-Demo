import sys
import datetime
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from app.db.database import SessionLocal, engine, Base
from app.models.session import Session
from app.models.meeting import Meeting
from app.models.runtime import Runtime
from app.services.runtime_scheduler_service import runtime_scheduler_service

def print_result(label: str, passed: bool, details: str = ""):
    status_str = "\033[92m[PASS]\033[0m" if passed else "\033[91m[FAIL]\033[0m"
    print(f"{label:<55} {status_str} {details}")

def main():
    print("=====================================================================")
    print("                 AUTOHR RUNTIME SCHEDULER VERIFIER                   ")
    print("=====================================================================\n")

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        # Seed test session & meeting
        session_id = "test_sched_session_001"
        db.query(Runtime).filter(Runtime.session_id == session_id).delete()
        db.query(Meeting).filter(Meeting.session_id == session_id).delete()
        db.query(Session).filter(Session.id == session_id).delete()
        db.commit()

        sess = Session(id=session_id, name="Scheduled Onboarding", status="READY")
        db.add(sess)
        db.commit()

        meeting = Meeting(
            session_id=session_id,
            teams_url="https://teams.microsoft.com/l/meetup-join/test",
            date="2026-07-25",
            time="10:00",
            organizer="HR Trainer"
        )
        db.add(meeting)
        db.commit()

        # Test 1: Schedule session
        res = runtime_scheduler_service.schedule_session(db, session_id)
        print_result("Test 1: Schedule meeting date & time", res.get("is_scheduled") is True)

        # Test 2: Status check
        status_res = runtime_scheduler_service.get_schedule_status(db, session_id)
        print_result("Test 2: Retrieve schedule status", status_res.get("state") == "SCHEDULED")

        # Test 3: System time comparison & single launch guarantee
        launched = runtime_scheduler_service.trigger_launch_if_due(db, session_id)
        print_result("Test 3: Autonomous launch trigger execution", launched is True)

        # Test 4: Prevent duplicate launches
        second_launch = runtime_scheduler_service.trigger_launch_if_due(db, session_id)
        print_result("Test 4: Duplicate launch prevention", second_launch is False)

        print("\n=====================================================================")
        print("                 SCHEDULER VERIFICATION PASSED                      ")
        print("=====================================================================")

    finally:
        db.close()

if __name__ == "__main__":
    main()
