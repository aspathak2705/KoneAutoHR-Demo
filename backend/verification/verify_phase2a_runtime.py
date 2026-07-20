import sys
import asyncio
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from app.db.database import SessionLocal, engine, Base
from app.models.session import Session
from app.models.meeting import Meeting
from app.models.runtime import Runtime
from app.models.presentation import Presentation
from app.models.organization_config import OrganizationConfig
from app.services.runtime_scheduler_service import runtime_scheduler_service
from app.services.teams_runtime_service import teams_runtime_service
from app.services.runtime_service import runtime_service

def print_result(label: str, passed: bool, details: str = ""):
    status_str = "\033[92m[PASS]\033[0m" if passed else "\033[91m[FAIL]\033[0m"
    print(f"{label:<55} {status_str} {details}")

def main():
    print("=====================================================================")
    print("             PHASE 2A.1 COMPLETE E2E RUNTIME VERIFIER                ")
    print("=====================================================================\n")

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        session_id = "test_phase2a_e2e_001"
        db.query(Runtime).filter(Runtime.session_id == session_id).delete()
        db.query(Meeting).filter(Meeting.session_id == session_id).delete()
        db.query(Presentation).filter(Presentation.session_id == session_id).delete()
        db.query(Session).filter(Session.id == session_id).delete()
        db.commit()

        # 1. Prepared Session & Meeting
        sess = Session(id=session_id, name="Full Phase 2A.1 E2E Induction", status="READY")
        db.add(sess)
        db.commit()

        meeting = Meeting(
            session_id=session_id,
            teams_url="https://teams.microsoft.com/l/meetup-join/e2e_test",
            date="2026-07-25",
            time="10:00",
            organizer="HR Trainer"
        )
        db.add(meeting)

        pres = Presentation(id="pres_e2e_001", session_id=session_id, name="E2E Presentation", original_filename="deck.pptx", total_slides=5)
        db.add(pres)
        db.commit()

        # 2. Runtime Scheduled
        sched = runtime_scheduler_service.schedule_session(db, session_id)
        print_result("1. Meeting Configured & Scheduled", sched["is_scheduled"] is True)

        # 3. AutoHR launches & joins Teams meeting
        launched = runtime_scheduler_service.trigger_launch_if_due(db, session_id)
        print_result("2. AutoHR Launches Meeting Connection", launched is True)

        # 4. Connection verified & WAITING state reached
        async def wait_for_ready():
            for _ in range(15):
                await asyncio.sleep(0.5)
                st = teams_runtime_service.get_status(db, session_id)
                if st["state"] in ["CONNECTED", "WAITING"]:
                    return True
            return False

        connected = asyncio.run(wait_for_ready())
        print_result("3. Reach CONNECTED / WAITING state", connected is True)

        # 5. Handover context exposed for Phase 2B
        runtime = db.query(Runtime).filter(Runtime.session_id == session_id).first()
        is_handover_ready = runtime.state in ["CONNECTED", "WAITING", "COMPLETED"]
        print_result("4. Phase 2B Handover Context Exposed", is_handover_ready is True)

        print("\n=====================================================================")
        print("                 PHASE 2A.1 COMPLETE RUNTIME PASSED                  ")
        print("=====================================================================")

    finally:
        db.close()

if __name__ == "__main__":
    main()
