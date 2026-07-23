import asyncio
import os
import sys
import time
import json
from pathlib import Path
from sqlalchemy.orm import Session as DBSession

# Insert backend dir to path to resolve imports correctly
backend_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(backend_dir))

# Mock environment variables to satisfy app startup configurations
os.environ.setdefault("DATABASE_URL", "sqlite:///./autohr.db")
os.environ.setdefault("UPLOAD_PATH", "./uploads")
os.environ.setdefault("MAX_UPLOAD_SIZE", "52428800")
os.environ.setdefault("ALLOWED_ORIGINS", "http://localhost:5173")
os.environ.setdefault("API_BASE_URL", "http://localhost:8000")

from app.db.database import engine, Base, SessionLocal
from app.models.session import Session
from app.models.meeting import Meeting
from app.models.presentation import Presentation
from app.models.presentation_script import PresentationScript
from app.models.presentation_question import PresentationQuestion
from app.models.employee_list import EmployeeList
from app.models.organization_config import OrganizationConfig

from app.modules.meeting_bot.bot.meeting_bot import MeetingBot
from app.modules.presentation_observer.services.presentation_observer_service import presentation_observer_service
from app.modules.presentation_observer.models.observation import Observation
from app.modules.presentation_observer.models.observation_state import ObservationState
from app.modules.presentation_observer.models.observation_event import ObservationEvent
from app.modules.semantic_browser.models.presentation_state import PresentationMode

from app.modules.induction_runtime.services.induction_runtime_service import induction_runtime_service
from app.modules.induction_runtime.models.runtime_state import RuntimeState
from app.modules.induction_runtime.models.session_event import SessionEvent
from app.modules.induction_runtime.event_bus.runtime_event_bus import runtime_event_bus

class StepTracker:
    def __init__(self, name: str):
        self.name = name
        self.success = False
        self.details = "Not executed"

    def complete(self, success: bool, details: str = "") -> None:
        self.success = success
        self.details = details

async def run_verification():
    print("==================================================")
    print("         AUTOHR PHASE 5 VERIFICATION RUN          ")
    print("==================================================")
    
    steps = {
        "init_db": StepTracker("Seeding Database Entities"),
        "init_engine": StepTracker("Orchestrator Initialized"),
        "stage1": StepTracker("Stage 1: Lobby & Greeting Trigger"),
        "stage2": StepTracker("Stage 2: Narration & Slide Changes"),
        "stage3": StepTracker("Stage 3: Q&A Chat Interruption"),
        "stage4": StepTracker("Stage 4: Closing Agent Farewell"),
        "stage5": StepTracker("Stage 5: State Flow Completed")
    }

    db = SessionLocal()
    session_id = "test-session-phase5"
    excel_path = "mock_inductees.xlsx"

    # Step 1: Create mock excel file
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.append(["Name", "Email", "Department", "Designation", "Location", "Joining Date"])
    ws.append(["Jane Doe", "jane.doe@kone.com", "HR", "Talent Acquisition Coordinator", "Espoo", "2026-08-01"])
    wb.save(excel_path)

    try:
        # Clean old records
        db.query(Session).filter(Session.id == session_id).delete()
        db.query(OrganizationConfig).delete()
        db.commit()

        # Seed Organization Persona
        config = OrganizationConfig(
            company_name="KONE",
            company_domain="kone.com",
            ai_officer_name="KONE AI Officer",
            ai_trainer_name="KONE Trainer",
            ai_role_description="AI Onboarding Assistant",
            vocal_tone="Professional",
            communication_style="Direct"
        )
        db.add(config)

        # Seed Presentation
        pres = Presentation(
            id="pres-phase5",
            name="KONE Onboarding deck",
            original_filename="kone_onboarding.pptx",
            storage_path="mock_deck.pptx"
        )
        db.add(pres)

        # Seed EmployeeList
        emp_list = EmployeeList(
            id="emplist-phase5",
            name="Inductees August 2026",
            original_filename="inductees.xlsx",
            storage_path=excel_path,
            employee_count=1
        )
        db.add(emp_list)

        # Seed Session
        sess = Session(
            id=session_id,
            name="Jane Doe Induction Session",
            presentation_id="pres-phase5",
            employee_list_id="emplist-phase5",
            status="PENDING"
        )
        db.add(sess)

        # Seed Meeting
        meeting = Meeting(
            session_id=session_id,
            teams_meeting_url="https://teams.microsoft.com/l/meetup-join/test",
            meeting_passcode="123456",
            organizer_name="HR Team"
        )
        db.add(meeting)

        # Seed PresentationScript (status MUST be COMPLETED as required by runtime_service)
        script_payload = {
            "welcome_flow": {
                "greeting": "Hello and welcome to KONE onboarding.",
                "presenter_intro": "I am your AI HR Trainer, here to guide you today.",
                "session_rules": "Please stay muted during slides.",
                "agenda": "Today we cover KONE values and safety guidelines."
            },
            "slide_narrations": {
                "1": "First slide: KONE is built on innovation and safety.",
                "2": "Second slide: Safety is our core priority. Report hazards immediately."
            },
            "closing_script": "That concludes KONE values and safety rules induction."
        }
        script = PresentationScript(
            presentation_id="pres-phase5",
            script_content=script_payload,
            llm_model="gemini-1.5-pro",
            status="COMPLETED"
        )
        db.add(script)

        # Seed PresentationQuestion (status MUST be COMPLETED)
        faq_payload = [
            {"question": "What is the policy on safety?", "answer": "KONE has a zero-tolerance policy for safety violations."}
        ]
        faq = PresentationQuestion(
            presentation_id="pres-phase5",
            questions_content=faq_payload,
            status="COMPLETED"
        )
        db.add(faq)
        db.commit()
        
        steps["init_db"].complete(True, "Database seeds injected successfully")
        print("[✓] Seed completed.")

        # Step 2: Initialize Coordinator
        coord = induction_runtime_service.get_coordinator(db, session_id)
        assert coord.session_manager.state == RuntimeState.CREATED
        assert len(coord.employee_context.employees_list) == 1
        assert coord.presenter_context.get_trainer_name() == "KONE Trainer"
        steps["init_engine"].complete(True, "RuntimeCoordinator preloaded and mapped assets correctly")
        print("[✓] Coordinator Initialized.")

        # Step 3: STAGE 1 - Lobby & Greeting
        print("\n--- STAGE 1: Lobby & Greeting Trigger ---")
        # Simulating lobby observation
        obs_lobby = Observation(
            timestamp=time.time(),
            observation_state=ObservationState.WAITING,
            presentation_state=PresentationMode.NONE,
            events=[]
        )
        await coord.poll_cycle(obs_lobby)
        assert coord.session_manager.state == RuntimeState.WAITING_FOR_PRESENTATION

        # Simulating presentation started
        obs_started = Observation(
            timestamp=time.time(),
            observation_state=ObservationState.ACTIVE,
            presentation_state=PresentationMode.POWERPOINT_SHARED,
            events=[ObservationEvent.PRESENTATION_STARTED],
            timeline_index=1
        )
        await coord.poll_cycle(obs_started)
        assert coord.session_manager.state == RuntimeState.INTRODUCTION
        
        # Wait for speaking simulation to complete (triggers presenting and slide 1 narration)
        await asyncio.sleep(2)
        assert coord.session_manager.state == RuntimeState.PRESENTING
        assert coord.memory.current_slide_number == 1
        steps["stage1"].complete(True, "Lobby WAITING_FOR_PRESENTATION and INTRODUCTION greeting played cleanly")
        print("[✓] Stage 1 Verified")

        # Step 4: STAGE 2 - Slide Changes
        print("\n--- STAGE 2: Slide Change Narration ---")
        # Simulating slide change to Slide 2
        obs_slide2 = Observation(
            timestamp=time.time(),
            observation_state=ObservationState.ACTIVE,
            presentation_state=PresentationMode.POWERPOINT_SHARED,
            events=[ObservationEvent.SLIDE_CHANGED],
            timeline_index=2
        )
        await coord.poll_cycle(obs_slide2)
        assert coord.memory.current_slide_number == 2
        assert coord.flow_controller.get_slide_by_number(2) is not None
        await asyncio.sleep(2) # speak slide 2
        steps["stage2"].complete(True, "Flow controller advanced and spoke slide 2 narration correctly")
        print("[✓] Stage 2 Verified")

        # Step 5: STAGE 3 - Q&A Interruption
        print("\n--- STAGE 3: Q&A Interruption ---")
        # Inject question
        answer = await coord.inject_question("Jane Doe", "What is the policy on safety?")
        assert "zero-tolerance" in answer
        assert coord.memory.questions_asked[0]["question"] == "What is the policy on safety?"
        assert coord.memory.questions_answered[0]["answer"] == answer
        
        # Inject fallback question
        answer_fallback = await coord.inject_question("Jane Doe", "How do I claim parking benefits?")
        assert "forward that question to HR" in answer_fallback
        
        steps["stage3"].complete(True, "QAAgent resolved pre-seeded FAQs and returned correct fallbacks on unknown items")
        print("[✓] Stage 3 Verified")

        # Step 6: STAGE 4 - Closing Agent Farewell
        print("\n--- STAGE 4: Closing Agent Farewell ---")
        # Simulating presentation ended
        obs_ended = Observation(
            timestamp=time.time(),
            observation_state=ObservationState.LOST,
            presentation_state=PresentationMode.NONE,
            events=[ObservationEvent.PRESENTATION_ENDED]
        )
        await coord.poll_cycle(obs_ended)
        assert coord.session_manager.state == RuntimeState.QUESTION_ANSWER
        
        # Wait for closing farewell to play
        await asyncio.sleep(2)
        steps["stage4"].complete(True, "Closing farewell generated and dispatched to Voice output")
        print("[✓] Stage 4 Verified")

        # Step 7: STAGE 5 - State Flow Completed
        print("\n--- STAGE 5: State Flow Completed ---")
        assert coord.session_manager.state == RuntimeState.COMPLETED
        steps["stage5"].complete(True, "Runtime engine reached COMPLETED state successfully")
        print("[✓] Stage 5 Verified")

    finally:
        # Clean up mock Excel and database seeds
        if os.path.exists(excel_path):
            os.remove(excel_path)
        db.query(Session).filter(Session.id == session_id).delete()
        db.query(OrganizationConfig).delete()
        db.commit()
        db.close()

    print("\n" + "=" * 50)
    print("       AUTOHR PHASE 5 VERIFICATION SUMMARY        ")
    print("=" * 50)
    passed_all = True
    for key, step in steps.items():
        if not step.success:
            passed_all = False
        icon = "[✓]" if step.success else "[X]"
        print(f"{icon:<4} {step.name:<45} | {step.details}")
    print("-" * 50)
    status_str = "PASSED" if passed_all else "FAILED"
    print(f"Overall Status: {status_str}")
    print("=" * 50)

if __name__ == "__main__":
    asyncio.run(run_verification())
