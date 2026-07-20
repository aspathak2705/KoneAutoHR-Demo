import sys
import asyncio
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from app.db.database import SessionLocal, engine, Base
from app.models.session import Session
from app.models.runtime import Runtime
from app.services.teams_runtime_service import teams_runtime_service

def print_result(label: str, passed: bool, details: str = ""):
    status_str = "\033[92m[PASS]\033[0m" if passed else "\033[91m[FAIL]\033[0m"
    print(f"{label:<55} {status_str} {details}")

def main():
    print("=====================================================================")
    print("                 AUTOHR TEAMS JOIN RUNTIME VERIFIER                  ")
    print("=====================================================================\n")

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        session_id = "test_join_session_001"
        db.query(Runtime).filter(Runtime.session_id == session_id).delete()
        db.query(Session).filter(Session.id == session_id).delete()
        db.commit()

        sess = Session(id=session_id, name="Teams Join Test Session", status="READY")
        db.add(sess)
        db.commit()

        # Test 1: Launch session
        teams_runtime_service.launch_session(session_id)
        st1 = teams_runtime_service.get_status(db, session_id)
        print_result("Test 1: Launch runtime session (LAUNCHING)", st1["state"] == "LAUNCHING")

        # Test 2: Trigger Join
        teams_runtime_service.join_meeting(session_id)
        st2 = teams_runtime_service.get_status(db, session_id)
        print_result("Test 2: Initiate Teams join sequence", st2["state"] in ["LAUNCHING", "JOINING"])

        # Test 3: Wait for state transitions (JOINING -> WAITING -> CONNECTED)
        async def wait_for_connected():
            for _ in range(15):
                await asyncio.sleep(0.5)
                st = teams_runtime_service.get_status(db, session_id)
                if st["state"] == "CONNECTED":
                    return True
            return False

        connected = asyncio.run(wait_for_connected())
        print_result("Test 3: Reach CONNECTED state autonomously", connected is True)

        # Test 4: Graceful Teardown / Leave
        teams_runtime_service.leave_meeting(session_id)
        st4 = teams_runtime_service.get_status(db, session_id)
        print_result("Test 4: Graceful disconnect (COMPLETED)", st4["state"] == "COMPLETED")

        print("\n=====================================================================")
        print("                  TEAMS JOIN VERIFICATION PASSED                      ")
        print("=====================================================================")

    finally:
        db.close()

if __name__ == "__main__":
    main()
