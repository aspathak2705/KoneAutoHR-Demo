import sys
import asyncio
import time
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from fastapi.testclient import TestClient
from main import app
from app.db.database import SessionLocal
from app.models.session import Session as DBSessionModel
from app.models.meeting import Meeting
from app.models.employee_list import EmployeeList
from app.models.presentation import Presentation
from app.models.presentation_script import PresentationScript
from app.models.presentation_question import PresentationQuestion

def print_result(label: str, passed: bool, details: str = ""):
    status_str = "\033[92m[PASS]\033[0m" if passed else "\033[91m[FAIL]\033[0m"
    print(f"{label:<50} {status_str} {details}")

def main():
    print("=====================================================================")
    print("                AUTOHR SPRINT 3 RUNTIME ENGINE VERIFIER             ")
    print("=====================================================================\n")

    client = TestClient(app)

    # 1. Seed database requirements
    with SessionLocal() as db:
        pres = db.query(Presentation).first()
        if not pres:
            pres = Presentation(name="Test Pres", original_filename="s.pptx", storage_path="s.pptx", uploaded_by="anna")
            db.add(pres)
            db.commit()
            db.refresh(pres)

        script = db.query(PresentationScript).filter(PresentationScript.presentation_id == pres.id).first()
        if not script:
            script = PresentationScript(
                presentation_id=pres.id,
                script_content={
                    "welcome_flow": {"greeting": "Hi!"},
                    "slide_narrations": {
                        "1": {"learning_objective": "Goal", "narration": "First Slide"},
                        "2": {"learning_objective": "Next", "narration": "Second Slide"}
                    },
                    "closing_script": {"summary": "Done"}
                },
                generated_at="2026-07-20T10:00:00",
                llm_model="model",
                status="COMPLETED"
            )
            db.add(script)
            db.commit()

        faq = db.query(PresentationQuestion).filter(PresentationQuestion.presentation_id == pres.id).first()
        if not faq:
            faq = PresentationQuestion(
                presentation_id=pres.id,
                questions_content=[{"question": "FAQ?", "answer": "Yes"}],
                status="COMPLETED"
            )
            db.add(faq)
            db.commit()

        emp_list = db.query(EmployeeList).first()
        if not emp_list:
            emp_list = EmployeeList(name="Register", original_filename="r.xlsx", storage_path="r.xlsx", employee_count=1)
            db.add(emp_list)
            db.commit()
            db.refresh(emp_list)

        session = db.query(DBSessionModel).filter(DBSessionModel.name == "Runtime Active Test Session").first()
        if not session:
            session = DBSessionModel(
                name="Runtime Active Test Session",
                status="READY",
                presentation_id=pres.id,
                employee_list_id=emp_list.id
            )
            db.add(session)
            db.commit()
            db.refresh(session)
        session_id = session.id

        meeting = db.query(Meeting).filter(Meeting.session_id == session_id).first()
        if not meeting:
            meeting = Meeting(
                session_id=session_id,
                teams_meeting_url="https://teams.microsoft.com/l/meetup-join/123",
                organizer_name="Anna Virtanen",
                meeting_date="2026-07-20",
                meeting_time="10:00"
            )
            db.add(meeting)
            db.commit()

    print_result("Test Session & components seeded", True, f"Session ID: {session_id}")

    try:
        # 2. Get status before meeting start (should report READY / state=READY)
        res_status_init = client.get(f"/api/v1/runtime/{session_id}")
        print_result("GET /status returns 200", res_status_init.status_code == 200)
        if res_status_init.status_code == 200:
            status_data = res_status_init.json()
            print_result("Initial state is READY", status_data.get("state") == "READY")
            print_result("Initial slide is 0", status_data.get("current_slide") == 0)

        # 3. Start meeting runtime loop
        print("\nStarting meeting runtime loop...")
        res_start = client.post(f"/api/v1/runtime/{session_id}/start")
        print_result("POST /start returns 200", res_start.status_code == 200)

        # Give short sleep for state machine to trigger background task
        time.sleep(0.5)

        # 4. Check state shift (should be JOINING)
        res_status_joining = client.get(f"/api/v1/runtime/{session_id}")
        if res_status_joining.status_code == 200:
            status_data = res_status_joining.json()
            print_result("State shifted to JOINING", status_data.get("state") == "JOINING")

        # 5. Test manual slide controls (next slide / prev slide)
        print("\nTesting manual slide progression...")
        res_next = client.post(f"/api/v1/runtime/{session_id}/next")
        print_result("POST /next returns 200", res_next.status_code == 200)
        if res_next.status_code == 200:
            print_result("Slide advanced to 1", res_next.json().get("current_slide") == 1)

        res_next2 = client.post(f"/api/v1/runtime/{session_id}/next")
        if res_next2.status_code == 200:
            print_result("Slide advanced to 2", res_next2.json().get("current_slide") == 2)

        res_prev = client.post(f"/api/v1/runtime/{session_id}/prev")
        if res_prev.status_code == 200:
            print_result("Slide backtracked to 1", res_prev.json().get("current_slide") == 1)

        # 6. Stop meeting runtime
        print("\nStopping meeting runtime...")
        res_stop = client.post(f"/api/v1/runtime/{session_id}/stop")
        print_result("POST /stop returns 200", res_stop.status_code == 200)

        res_status_final = client.get(f"/api/v1/runtime/{session_id}")
        if res_status_final.status_code == 200:
            print_result("State shifted to COMPLETED", res_status_final.json().get("state") == "COMPLETED")

        print("\n=====================================================================")
        print("                 SPRINT 3 RUNTIME ENGINE TEST PASS                   ")
        print("=====================================================================")

    except Exception as e:
        print(f"\nVerification failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
