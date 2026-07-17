import sys
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
    print("                AUTOHR SPRINT 2 RUNTIME VERIFIER                    ")
    print("=====================================================================\n")

    client = TestClient(app)

    # Seed all models so that Sprint 2 runtime loader can load the context
    with SessionLocal() as db:
        # Create presentation
        pres = db.query(Presentation).first()
        if not pres:
            pres = Presentation(
                name="Test Presentation",
                original_filename="slides.pptx",
                storage_path="slides.pptx",
                uploaded_by="anna"
            )
            db.add(pres)
            db.commit()
            db.refresh(pres)

        # Create script
        script = db.query(PresentationScript).filter(PresentationScript.presentation_id == pres.id).first()
        if not script:
            script = PresentationScript(
                presentation_id=pres.id,
                script_content={
                    "welcome_flow": {"greeting": "Welcome to Kone!"},
                    "slide_narrations": {"1": {"learning_objective": "Goal", "narration": "First Slide"}},
                    "closing_script": {"summary": "Closing Summary"}
                },
                generated_at=datetime_now := datetime_now if 'datetime_now' in locals() else "2026-07-20T10:00:00",
                llm_model="model",
                status="COMPLETED"
            )
            db.add(script)
            db.commit()

        # Create faq
        faq = db.query(PresentationQuestion).filter(PresentationQuestion.presentation_id == pres.id).first()
        if not faq:
            faq = PresentationQuestion(
                presentation_id=pres.id,
                questions_content=[{"question": "What is KONE?", "answer": "Elevator company"}],
                status="COMPLETED"
            )
            db.add(faq)
            db.commit()

        # Create employee list
        emp_list = db.query(EmployeeList).first()
        if not emp_list:
            emp_list = EmployeeList(
                name="Employee Register",
                original_filename="register.xlsx",
                storage_path=str(backend_dir / "uploads" / "employees" / "register.xlsx"),
                employee_count=1
            )
            db.add(emp_list)
            db.commit()
            db.refresh(emp_list)

        # Create session
        session = db.query(DBSessionModel).filter(DBSessionModel.name == "Runtime Test Session").first()
        if not session:
            session = DBSessionModel(
                name="Runtime Test Session",
                status="READY",
                presentation_id=pres.id,
                employee_list_id=emp_list.id
            )
            db.add(session)
            db.commit()
            db.refresh(session)
        session_id = session.id

        # Create meeting
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

    print_result("Test Session & meeting seeded", True, f"Session ID: {session_id}")

    try:
        # 1. Fetch `/runtime/{session_id}/context`
        print("\nLoading runtime context...")
        # Patch parse_employees_excel to return a mock list for context loader testing
        from unittest.mock import patch
        mock_employees = [{"name": "Matti Nykänen", "email": "matti@kone.com", "department": "Engineering"}]
        with patch("app.services.runtime_service.parse_employees_excel", return_value=mock_employees):
            res_context = client.get(f"/api/v1/runtime/{session_id}/context")
            print_result("GET /context returns 200", res_context.status_code == 200)
            if res_context.status_code == 200:
                ctx = res_context.json()
                print_result("Context has loaded employees", len(ctx.get("employees", [])) == 1)
                print_result("Context has loaded meeting URL", ctx.get("meeting", {}).get("teams_meeting_url") == "https://teams.microsoft.com/l/meetup-join/123")
                print_result("Context has script content", "slide_narrations" in ctx.get("script", {}))

            # 2. Fetch `/runtime/{session_id}/voice-config`
            print("\nLoading voice configuration...")
            res_voice = client.get(f"/api/v1/runtime/{session_id}/voice-config")
            print_result("GET /voice-config returns 200", res_voice.status_code == 200)
            if res_voice.status_code == 200:
                voice = res_voice.json()
                print_result("Voice configuration has TTS/STT settings", "tts_provider" in voice and "stt_provider" in voice)

            # 3. Fetch `/runtime/{session_id}/slide-controller`
            print("\nLoading slide controller configurations...")
            res_slides = client.get(f"/api/v1/runtime/{session_id}/slide-controller")
            print_result("GET /slide-controller returns 200", res_slides.status_code == 200)
            if res_slides.status_code == 200:
                ctrl = res_slides.json()
                print_result("Slide controller has total slide count", ctrl.get("total_slides") == 1)

            # 4. Fetch `/runtime/{session_id}` summary
            print("\nLoading runtime readiness summary...")
            res_readiness = client.get(f"/api/v1/runtime/{session_id}")
            print_result("GET /runtime/{session_id} returns 200", res_readiness.status_code == 200)
            if res_readiness.status_code == 200:
                summary = res_readiness.json()
                print_result("Summary reports presentation is ready", summary.get("presentation_ready") is True)
                print_result("Summary reports meeting is ready", summary.get("meeting_ready") is True)

        print("\n=====================================================================")
        print("                 SPRINT 2 RUNTIME TEST PASS                          ")
        print("=====================================================================")

    except Exception as e:
        print(f"\nVerification failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
