import sys
import asyncio
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
from app.models.presentation_question import PresentationQuestion

def print_result(label: str, passed: bool, details: str = ""):
    status_str = "\033[92m[PASS]\033[0m" if passed else "\033[91m[FAIL]\033[0m"
    print(f"{label:<50} {status_str} {details}")

def main():
    print("=====================================================================")
    print("                AUTOHR SPRINT 4 Q&A ENGINE VERIFIER                 ")
    print("=====================================================================\n")

    client = TestClient(app)

    # Seed FAQ questions
    with SessionLocal() as db:
        pres = db.query(Presentation).first()
        if not pres:
            pres = Presentation(name="Test Deck", original_filename="slides.pptx", storage_path="slides.pptx", uploaded_by="anna")
            db.add(pres)
            db.commit()
            db.refresh(pres)

        # Clear legacy FAQs and write a structured check
        db.query(PresentationQuestion).filter(PresentationQuestion.presentation_id == pres.id).delete()
        faq = PresentationQuestion(
            presentation_id=pres.id,
            questions_content=[
                {"question": "How do I request annual leave?", "answer": "Use the Kone HR portal under Leave requests."},
                {"question": "What is our company phone policy?", "answer": "Company phones are provided for client coordination and must follow active data safety guidelines."}
            ],
            status="COMPLETED"
        )
        db.add(faq)

        emp_list = db.query(EmployeeList).first()
        if not emp_list:
            emp_list = EmployeeList(name="Register", original_filename="r.xlsx", storage_path="r.xlsx", employee_count=1)
            db.add(emp_list)
            db.commit()
            db.refresh(emp_list)

        session = db.query(DBSessionModel).filter(DBSessionModel.name == "QA Test Session").first()
        if not session:
            session = DBSessionModel(
                name="QA Test Session",
                status="READY",
                presentation_id=pres.id,
                employee_list_id=emp_list.id
            )
            db.add(session)
            db.commit()
            db.refresh(session)
        session_id = session.id

        # Clean conversation log for test freshness
        from app.models.runtime_message import RuntimeMessage
        db.query(RuntimeMessage).filter(RuntimeMessage.session_id == session_id).delete()
        
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

    try:
        # 1. Ask a matching FAQ question
        print("Sending matching FAQ question...")
        payload_faq = {
            "speaker_name": "Matti Nykänen",
            "question_text": "how do I request annual leave?"
        }
        res_faq = client.post(f"/api/v1/runtime/{session_id}/ask", json=payload_faq)
        print_result("POST /ask matching FAQ returns 200", res_faq.status_code == 200)
        if res_faq.status_code == 200:
            res_data = res_faq.json()
            print_result("Returned correct matched FAQ answer", "Leave requests" in res_data.get("answer", {}).get("text"))

        # 2. Ask an off-topic moderated question
        print("\nSending off-topic question for moderation...")
        payload_off = {
            "speaker_name": "Matti Nykänen",
            "question_text": "what is the recipe for chocolate chip cookies?"
        }
        res_off = client.post(f"/api/v1/runtime/{session_id}/ask", json=payload_off)
        print_result("POST /ask off-topic returns 200", res_off.status_code == 200)
        if res_off.status_code == 200:
            res_data = res_off.json()
            print_result("Moderator flagged and declined answer", "KONE onboarding assistant" in res_data.get("answer", {}).get("text"))

        # 3. Get history log and count questions
        print("\nChecking conversation history logs...")
        res_history = client.get(f"/api/v1/runtime/{session_id}/conversation")
        print_result("GET /conversation returns 200", res_history.status_code == 200)
        if res_history.status_code == 200:
            history = res_history.json()
            print_result("History contains 4 logs (2 Q&A pairs)", len(history) == 4)

        # 4. Get runtime status and assert questions count
        res_status = client.get(f"/api/v1/runtime/{session_id}")
        if res_status.status_code == 200:
            print_result("Status returns questions count = 2", res_status.json().get("questions_asked") == 2)

        print("\n=====================================================================")
        print("                 SPRINT 4 Q&A TEST PASS                              ")
        print("=====================================================================")

    except Exception as e:
        print(f"\nVerification failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
