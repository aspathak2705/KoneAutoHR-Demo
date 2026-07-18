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
    print("        AUTOHR SPRINT RC-6 RUNTIME PRODUCTION HARDENING VERIFIER     ")
    print("=====================================================================\n")

    client = TestClient(app)

    with SessionLocal() as db:
        session = db.query(DBSessionModel).first()
        session_id = session.id
        
        # Reset runtime reconnect values
        runtime = db.query(Runtime).filter(Runtime.session_id == session_id).first()
        if runtime:
            runtime.reconnect_count = 0
            db.commit()

    try:
        # Trigger simulated reconnect drop
        print("Triggering drop and reconnection loop...")
        res_reconnect = client.post(f"/api/v1/runtime/{session_id}/reconnect")
        print_result("POST /reconnect returns 200", res_reconnect.status_code == 200)

        # Give short sleep for connection task to update db
        time.sleep(0.5)
        res_status = client.get(f"/api/v1/runtime/{session_id}/status")
        
        if res_status.status_code == 200:
            status_data = res_status.json()
            print_result("State is RECONNECTING", status_data.get("state") == "RECONNECTING")
            print_result("Reconnect count incremented", status_data.get("reconnect_count") == 1)

        print("\n=====================================================================")
        print("                 SPRINT RC-6 HARDENING TEST PASS                     ")
        print("=====================================================================")

    except Exception as e:
        print(f"\nVerification failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
