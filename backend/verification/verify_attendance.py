import sys
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from fastapi.testclient import TestClient
from main import app
from app.db.database import SessionLocal
from app.models.session import Session as DBSessionModel
from app.models.attendance import Attendance

def print_result(label: str, passed: bool, details: str = ""):
    status_str = "\033[92m[PASS]\033[0m" if passed else "\033[91m[FAIL]\033[0m"
    print(f"{label:<50} {status_str} {details}")

def main():
    print("=====================================================================")
    print("            AUTOHR SPRINT RC-3 ATTENDANCE RUNTIME VERIFIER           ")
    print("=====================================================================\n")

    client = TestClient(app)

    with SessionLocal() as db:
        session = db.query(DBSessionModel).first()
        session_id = session.id
        
        # Clean and seed a mock attendance log
        db.query(Attendance).filter(Attendance.session_id == session_id).delete()
        
        att = Attendance(
            session_id=session_id,
            attendee_name="Matti Nykänen",
            attendee_email="matti@kone.com",
            duration_seconds=1500, # 25 minutes
            questions_asked=2,
            status="PRESENT"
        )
        db.add(att)
        db.commit()

    try:
        # Get attendance report
        res_att = client.get(f"/api/v1/runtime/{session_id}/attendance")
        print_result("GET /attendance returns 200", res_att.status_code == 200)
        
        if res_att.status_code == 200:
            summary = res_att.json()
            print_result("Total joined is 1", summary.get("joined") == 1)
            print_result("Presenter completed count is 1", summary.get("completed_present") == 1)
            
            attendees = summary.get("attendees", [])
            print_result("First attendee matches name", attendees[0].get("name") == "Matti Nykänen")
            print_result("First attendee questions count is 2", attendees[0].get("questions_asked") == 2)
            print_result("First attendee status is PRESENT", attendees[0].get("status") == "PRESENT")

        print("\n=====================================================================")
        print("                 SPRINT RC-3 ATTENDANCE TEST PASS                    ")
        print("=====================================================================")

    except Exception as e:
        print(f"\nVerification failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
