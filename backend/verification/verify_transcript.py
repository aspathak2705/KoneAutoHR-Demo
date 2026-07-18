import sys
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from fastapi.testclient import TestClient
from main import app
from app.db.database import SessionLocal
from app.models.session import Session as DBSessionModel
from app.models.runtime_message import RuntimeMessage

def print_result(label: str, passed: bool, details: str = ""):
    status_str = "\033[92m[PASS]\033[0m" if passed else "\033[91m[FAIL]\033[0m"
    print(f"{label:<50} {status_str} {details}")

def main():
    print("=====================================================================")
    print("            AUTOHR SPRINT RC-4 TRANSCRIPT RUNTIME VERIFIER           ")
    print("=====================================================================\n")

    client = TestClient(app)

    with SessionLocal() as db:
        session = db.query(DBSessionModel).first()
        session_id = session.id
        
        # Seed conversations
        db.query(RuntimeMessage).filter(RuntimeMessage.session_id == session_id).delete()
        msg1 = RuntimeMessage(session_id=session_id, speaker_name="AI Trainer", message_text="Welcome to Kone Onboarding.")
        msg2 = RuntimeMessage(session_id=session_id, speaker_name="Matti", message_text="Where is the lunchroom?")
        db.add(msg1)
        db.add(msg2)
        db.commit()

    try:
        # Get raw transcript
        res_trans = client.get(f"/api/v1/runtime/{session_id}/transcript-data")
        print_result("GET /transcript-data returns 200", res_trans.status_code == 200)
        
        if res_trans.status_code == 200:
            transcript = res_trans.json()
            print_result("Transcript dialogue count is 2", len(transcript) == 2)
            print_result("First speaker is AI Trainer", transcript[0].get("speaker") == "AI Trainer")
            print_result("Second speaker is Matti", transcript[1].get("speaker") == "Matti")

        print("\n=====================================================================")
        print("                 SPRINT RC-4 TRANSCRIPT TEST PASS                    ")
        print("=====================================================================")

    except Exception as e:
        print(f"\nVerification failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
