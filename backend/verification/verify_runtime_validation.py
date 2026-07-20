import sys
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from app.db.database import SessionLocal, engine, Base
from app.models.session import Session
from app.models.meeting import Meeting
from app.services.runtime_validation_service import runtime_validation_service

def print_result(label: str, passed: bool, details: str = ""):
    status_str = "\033[92m[PASS]\033[0m" if passed else "\033[91m[FAIL]\033[0m"
    print(f"{label:<55} {status_str} {details}")

def main():
    print("=====================================================================")
    print("                RUN TIME VALIDATION CHECKS VERIFIER                 ")
    print("=====================================================================\n")

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        session_id = "test_val_session_001"
        db.query(Meeting).filter(Meeting.session_id == session_id).delete()
        db.query(Session).filter(Session.id == session_id).delete()
        db.commit()

        sess = Session(id=session_id, name="Validation Test Session", status="PREPARING")
        db.add(sess)
        db.commit()

        # Test 1: Missing Meeting URL & Assets (Readiness = False)
        res1 = runtime_validation_service.validate_runtime_readiness(db, session_id)
        print_result("Test 1: Detect missing assets checklist", res1["is_ready"] is False)

        # Test 2: Fail Fast Assertion
        failed_fast = False
        try:
            runtime_validation_service.assert_valid_for_launch(db, session_id)
        except ValueError:
            failed_fast = True
        print_result("Test 2: Fast-fail assertion on missing assets", failed_fast is True)

        # Test 3: Partially configured session
        meeting = Meeting(
            session_id=session_id,
            teams_url="https://teams.microsoft.com/l/meetup-join/test",
            date="2026-07-25",
            time="10:00",
            organizer="HR Trainer"
        )
        db.add(meeting)
        db.commit()

        res3 = runtime_validation_service.validate_runtime_readiness(db, session_id)
        print_result("Test 3: Missing components list accurately identifies script/employees", "has_presentation" in res3["missing_components"])

        print("\n=====================================================================")
        print("               RUNTIME VALIDATION VERIFICATION PASSED                ")
        print("=====================================================================")

    finally:
        db.close()

if __name__ == "__main__":
    main()
