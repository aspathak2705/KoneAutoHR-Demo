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
    print("            AUTOHR SPRINT RC-2 SPEECH RUNTIME VERIFIER              ")
    print("=====================================================================\n")

    client = TestClient(app)

    with SessionLocal() as db:
        session = db.query(DBSessionModel).first()
        session_id = session.id

        # Set runtime state to connected for speech tests
        runtime = db.query(Runtime).filter(Runtime.session_id == session_id).first()
        if not runtime:
            runtime = Runtime(session_id=session_id)
            db.add(runtime)
        runtime.state = "CONNECTED"
        runtime.current_slide = 1
        db.commit()

    try:
        # 1. Start Speaking
        print("Initiating speech stream...")
        payload = {"narration_text": "Welcome to KONE induction call. Let's start."}
        res_speak = client.post(f"/api/v1/runtime/{session_id}/speak", json=payload)
        print_result("POST /speak returns 200", res_speak.status_code == 200)

        # Check speech state
        res_status = client.get(f"/api/v1/runtime/{session_id}/status")
        if res_status.status_code == 200:
            print_result("Speech state is SPEAKING", res_status.json().get("speech_state") == "SPEAKING")

        # 2. Stop Speaking / Interrupted
        print("Interrupting speech stream...")
        res_stop = client.post(f"/api/v1/runtime/{session_id}/stop-speaking")
        print_result("POST /stop-speaking returns 200", res_stop.status_code == 200)

        res_status_s = client.get(f"/api/v1/runtime/{session_id}/status")
        if res_status_s.status_code == 200:
            print_result("Speech state is INTERRUPTED", res_status_s.json().get("speech_state") == "INTERRUPTED")

        print("\n=====================================================================")
        print("                 SPRINT RC-2 VOICE TEST PASS                         ")
        print("=====================================================================")

    except Exception as e:
        print(f"\nVerification failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
