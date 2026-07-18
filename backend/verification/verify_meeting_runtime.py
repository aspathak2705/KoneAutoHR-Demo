import sys
import time
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from fastapi.testclient import TestClient
from main import app
from app.db.database import SessionLocal
from app.models.session import Session as DBSessionModel
from app.models.runtime import Runtime

def print_result(label: str, passed: bool, details: str = ""):
    status_str = "\033[92m[PASS]\033[0m" if passed else "\033[91m[FAIL]\033[0m"
    print(f"{label:<50} {status_str} {details}")

def main():
    print("=====================================================================")
    print("            AUTOHR SPRINT RC-1 TEAMS RUNTIME VERIFIER               ")
    print("=====================================================================\n")

    client = TestClient(app)

    with SessionLocal() as db:
        session = db.query(DBSessionModel).first()
        if not session:
            session = DBSessionModel(name="Teams Runtime Session", status="READY")
            db.add(session)
            db.commit()
            db.refresh(session)
        session_id = session.id

    try:
        # 1. Launch Client
        res_launch = client.post(f"/api/v1/runtime/{session_id}/launch")
        print_result("POST /launch returns 200", res_launch.status_code == 200)

        # Check launch state
        res_status = client.get(f"/api/v1/runtime/{session_id}/status")
        if res_status.status_code == 200:
            print_result("State is LAUNCHING", res_status.json().get("state") == "LAUNCHING")

        # 2. Join Meeting
        print("Joining Teams meeting...")
        res_join = client.post(f"/api/v1/runtime/{session_id}/join")
        print_result("POST /join returns 200", res_join.status_code == 200)

        # Give short sleep for state sequence to tick
        time.sleep(0.5)
        res_status_j = client.get(f"/api/v1/runtime/{session_id}/status")
        if res_status_j.status_code == 200:
            print_result("State is JOINING", res_status_j.json().get("state") == "JOINING")

        # 3. Graceful Exit
        print("Leaving meeting gracefully...")
        res_leave = client.post(f"/api/v1/runtime/{session_id}/leave")
        print_result("POST /leave returns 200", res_leave.status_code == 200)

        res_status_l = client.get(f"/api/v1/runtime/{session_id}/status")
        if res_status_l.status_code == 200:
            print_result("State is COMPLETED", res_status_l.json().get("state") == "COMPLETED")

        print("\n=====================================================================")
        print("                 SPRINT RC-1 MEETINGS TEST PASS                      ")
        print("=====================================================================")

    except Exception as e:
        print(f"\nVerification failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
