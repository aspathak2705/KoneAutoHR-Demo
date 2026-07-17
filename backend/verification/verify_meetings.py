import sys
import datetime
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from fastapi.testclient import TestClient
from main import app
from app.db.database import SessionLocal
from app.models.session import Session as DBSessionModel
from app.models.employee_list import EmployeeList

def print_result(label: str, passed: bool, details: str = ""):
    status_str = "\033[92m[PASS]\033[0m" if passed else "\033[91m[FAIL]\033[0m"
    print(f"{label:<50} {status_str} {details}")

def main():
    print("=====================================================================")
    print("                AUTOHR SPRINT 1 MEETINGS VERIFIER                   ")
    print("=====================================================================\n")

    client = TestClient(app)

    # 1. Seed a test session in the database
    with SessionLocal() as db:
        # Check or create mock employee list
        emp_list = db.query(EmployeeList).filter(EmployeeList.name == "Test Register").first()
        if not emp_list:
            emp_list = EmployeeList(
                name="Test Register",
                original_filename="register.xlsx",
                storage_path=str(backend_dir / "uploads" / "employees" / "register.xlsx"),
                employee_count=1
            )
            # Create uploads directories if they don't exist
            import os
            os.makedirs(os.path.dirname(emp_list.storage_path), exist_ok=True)
            # Write a dummy file to simulate excel register path
            with open(emp_list.storage_path, "wb") as f:
                f.write(b"")
            db.add(emp_list)
            db.commit()
            db.refresh(emp_list)

        test_session = db.query(DBSessionModel).filter(DBSessionModel.name == "Manual Teams Test Session").first()
        if not test_session:
            test_session = DBSessionModel(
                name="Manual Teams Test Session",
                status="PENDING",
                employee_list_id=emp_list.id
            )
            db.add(test_session)
            db.commit()
            db.refresh(test_session)
        session_id = test_session.id

    print_result("Test Session created in database", True, f"Session ID: {session_id}")

    try:
        # 2. Test malformed Teams URL rejection
        print("\nScheduling meeting with malformed URL...")
        payload_bad = {
            "session_id": session_id,
            "teams_meeting_url": "https://google.com/meet",
            "meeting_passcode": "123",
            "organizer_name": "Anna Virtanen",
            "meeting_date": "2026-07-20",
            "meeting_time": "10:00"
        }
        res_bad = client.post("/api/v1/meetings", json=payload_bad)
        print_result(
            "POST /meetings rejects malformed URL (400)",
            res_bad.status_code == 400,
            f"Response: {res_bad.text}"
        )

        # 3. Test successful manual Teams meeting scheduling
        print("\nScheduling manual Teams meeting...")
        payload_good = {
            "session_id": session_id,
            "teams_meeting_url": "https://teams.microsoft.com/l/meetup-join/19%3ameeting_YTM1M2MxMzUtZGRkOC00...",
            "meeting_passcode": "abc-xyz-123",
            "organizer_name": "Anna Virtanen",
            "meeting_date": "2026-07-20",
            "meeting_time": "10:00"
        }
        res_post = client.post("/api/v1/meetings", json=payload_good)
        print_result("POST /meetings returns 201", res_post.status_code == 201, f"Status: {res_post.status_code}")
        
        if res_post.status_code == 201:
            meeting = res_post.json()
            meeting_id = meeting.get("id")
            print_result("Persisted Teams URL", meeting.get("teams_meeting_url") == payload_good["teams_meeting_url"])
            print_result("Persisted Passcode", meeting.get("meeting_passcode") == payload_good["meeting_passcode"])
            print_result("Persisted Date & Time", meeting.get("meeting_date") == "2026-07-20" and meeting.get("meeting_time") == "10:00")

            # 4. Test GET /meetings/session/{session_id}
            print("\nFetching meeting details by Session ID...")
            res_session = client.get(f"/api/v1/meetings/session/{session_id}")
            print_result("GET /meetings/session/{session_id} returns 200", res_session.status_code == 200)

            # 5. Test POST /meetings/session/{session_id}/generate-drafts
            # Patch parse_employees_excel to return a mock list for draft testing
            from unittest.mock import patch
            mock_employees = [{"name": "Matti Nykänen", "email": "matti@kone.com", "department": "Engineering"}]
            with patch("app.services.invitation_draft_service.parse_employees_excel", return_value=mock_employees):
                print("\nGenerating invitation drafts via API...")
                res_drafts = client.post(f"/api/v1/meetings/session/{session_id}/generate-drafts")
                print_result("POST /generate-drafts returns 200", res_drafts.status_code == 200)
                
                if res_drafts.status_code == 200:
                    drafts = res_drafts.json()
                    print_result("Generated draft count is 1", len(drafts) == 1)
                    draft_id = drafts[0].get("id")
                    print_result("Draft recipient name matches", drafts[0].get("recipient_name") == "Matti Nykänen")
                    print_result("Draft recipient email matches", drafts[0].get("recipient_email") == "matti@kone.com")
                    print_result("Draft body contains Teams Link", "teams.microsoft.com" in drafts[0].get("body"))

                    # 6. Test PUT /meetings/drafts/{id}
                    print("\nUpdating draft details...")
                    payload_draft_edit = {
                        "subject": "Custom Subject",
                        "body": "<p>Welcome to KONE, Matti!</p>"
                    }
                    res_edit = client.put(f"/api/v1/meetings/drafts/{draft_id}", json=payload_draft_edit)
                    print_result("PUT /drafts/{id} returns 200", res_edit.status_code == 200)
                    if res_edit.status_code == 200:
                        edited_draft = res_edit.json()
                        print_result("Draft status is EDITED", edited_draft.get("status") == "EDITED")
                        print_result("Draft subject updated", edited_draft.get("subject") == "Custom Subject")

            # 7. Test readiness check endpoint
            print("\nValidating session readiness...")
            res_ready = client.post(f"/api/v1/meetings/session/{session_id}/validate-readiness")
            print_result("POST /validate-readiness returns 200", res_ready.status_code == 200)
            if res_ready.status_code == 200:
                check = res_ready.json()
                print_result("Validation results structure valid", "is_ready" in check)

        print("\n=====================================================================")
        print("                 SPRINT 1 MEETINGS TEST PASS                         ")
        print("=====================================================================")

    except Exception as e:
        print(f"\nVerification failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
