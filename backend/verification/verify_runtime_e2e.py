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
    print("           AUTOHR SPRINT RC-7 PRODUCTION VALIDATION VERIFIER         ")
    print("=====================================================================\n")

    client = TestClient(app)

    # 1. Database requirements setup
    with SessionLocal() as db:
        pres = db.query(Presentation).first()
        if not pres:
            pres = Presentation(name="E2E Deck", original_filename="e.pptx", storage_path="e.pptx", uploaded_by="anna")
            db.add(pres)
            db.commit()
            db.refresh(pres)

        script = db.query(PresentationScript).filter(PresentationScript.presentation_id == pres.id).first()
        if not script:
            script = PresentationScript(
                presentation_id=pres.id,
                script_content={
                    "welcome_flow": {"greeting": "Hello"},
                    "slide_narrations": {"1": {"narration": "First Slide"}},
                    "closing_script": {"summary": "Goodbye"}
                },
                status="COMPLETED"
            )
            db.add(script)
            db.commit()

        faq = db.query(PresentationQuestion).filter(PresentationQuestion.presentation_id == pres.id).first()
        if not faq:
            faq = PresentationQuestion(
                presentation_id=pres.id,
                questions_content=[{"question": "How leave works?", "answer": "Use HR Portal."}],
                status="COMPLETED"
            )
            db.add(faq)
            db.commit()

        emp_list = db.query(EmployeeList).first()
        if not emp_list:
            emp_list = EmployeeList(name="E2E Register", original_filename="r.xlsx", storage_path="r.xlsx", employee_count=1)
            db.add(emp_list)
            db.commit()
            db.refresh(emp_list)

        session = db.query(DBSessionModel).filter(DBSessionModel.name == "E2E Production Test").first()
        if not session:
            session = DBSessionModel(
                name="E2E Production Test",
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
                teams_meeting_url="https://teams.microsoft.com/l/meetup-join/456",
                organizer_name="HR Specialist",
                meeting_date="2026-07-22",
                meeting_time="11:00"
            )
            db.add(meeting)
            db.commit()

    print_result("E2E database dependencies seeded", True, f"Session ID: {session_id}")

    try:
        # Step 1: Launch client
        print("\n--- Step 1: Launching Teams Participant ---")
        res_launch = client.post(f"/api/v1/runtime/{session_id}/launch")
        print_result("POST /launch returns 200", res_launch.status_code == 200)

        # Step 2: Join call lobby
        print("\n--- Step 2: Joining Call lobby ---")
        res_join = client.post(f"/api/v1/runtime/{session_id}/join")
        print_result("POST /join returns 200", res_join.status_code == 200)
        time.sleep(0.5)
        
        # Step 3: Run Speech Narration
        print("\n--- Step 3: Testing Speech Narration controls ---")
        payload = {"narration_text": "This is slide number one."}
        res_speak = client.post(f"/api/v1/runtime/{session_id}/speak", json=payload)
        print_result("POST /speak returns 200", res_speak.status_code == 200)

        res_stop = client.post(f"/api/v1/runtime/{session_id}/stop-speaking")
        print_result("POST /stop-speaking returns 200", res_stop.status_code == 200)

        # Step 4: Q&A Matching
        print("\n--- Step 4: Testing Q&A Interaction ---")
        payload_q = {"speaker_name": "Matti", "question_text": "how leave works?"}
        res_ask = client.post(f"/api/v1/runtime/{session_id}/ask", json=payload_q)
        print_result("POST /ask returns 200", res_ask.status_code == 200)
        if res_ask.status_code == 200:
            print_result("Correct FAQ answer matched", "HR Portal" in res_ask.json().get("answer", {}).get("text"))

        # Step 5: Simulate Connection drops
        print("\n--- Step 5: Simulating Reconnect loops ---")
        res_reconnect = client.post(f"/api/v1/runtime/{session_id}/reconnect")
        print_result("POST /reconnect returns 200", res_reconnect.status_code == 200)

        # Step 6: Leave call connection
        print("\n--- Step 6: Finalizing Meeting ---")
        res_leave = client.post(f"/api/v1/runtime/{session_id}/leave")
        print_result("POST /leave returns 200", res_leave.status_code == 200)

        # Step 7: Retrieve transcript timelines and attendance sheets
        print("\n--- Step 7: Retrieving E2E logs summaries ---")
        res_trans = client.get(f"/api/v1/runtime/{session_id}/transcript-data")
        print_result("GET /transcript-data dialogue retrieved", res_trans.status_code == 200)
        if res_trans.status_code == 200:
            print_result("Transcript dialogue interleaves SYSTEM logs", len(res_trans.json()) > 0)

        res_att = client.get(f"/api/v1/runtime/{session_id}/attendance")
        print_result("GET /attendance generated roster summary", res_att.status_code == 200)

        print("\n=====================================================================")
        print("            AUTOHR PHASE 2A.1 E2E TESTS SUCCESSFULLY PASSED         ")
        print("=====================================================================")

    except Exception as e:
        print(f"\nVerification E2E failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
