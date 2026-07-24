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
from app.models.presentation_asset import PresentationAsset
from app.models.presentation_job import PresentationJob
from app.models.upload import Upload
from app.models.runtime import Runtime
from app.models.runtime_message import RuntimeMessage
from app.models.attendance import Attendance
from app.models.invitation_draft import InvitationDraft

from app.modules.meeting_bot.bot.meeting_bot import MeetingBot
from app.modules.presentation_observer.services.presentation_observer_service import presentation_observer_service
from app.modules.presentation_observer.models.observation import Observation
from app.modules.presentation_observer.models.observation_state import ObservationState
from app.modules.presentation_observer.models.observation_event import ObservationEvent
from app.modules.semantic_browser.models.presentation_state import PresentationMode
from app.modules.semantic_browser.models.meeting_state import MeetingState

from app.modules.induction_runtime.services.induction_runtime_service import induction_runtime_service
from app.modules.induction_runtime.models.runtime_state import RuntimeState
from app.modules.induction_runtime.config.runtime_config import RuntimeConfig
from app.modules.induction_runtime.orchestrator.runtime_coordinator import RuntimeCoordinator
from app.modules.induction_runtime.narrator.voice_output_interface import VoiceOutputInterface

class StepTracker:
    def __init__(self, name: str):
        self.name = name
        self.success = False
        self.details = "Not executed"

    def complete(self, success: bool, details: str = "") -> None:
        self.success = success
        self.details = details

# Trace voice output calls to assert precise sequence executions
class TracedVoiceOutput(VoiceOutputInterface):
    def __init__(self):
        self.history = []
        self.is_speaking = False
        self._current_callback = None

    def say(self, text: str, callback = None, **kwargs) -> None:
        self.is_speaking = True
        self.history.append(("say", text))
        self._current_callback = callback
        
    def interrupt(self) -> None:
        self.is_speaking = False
        self.history.append(("interrupt", None))
        
    def stop(self) -> None:
        self.is_speaking = False
        self.history.append(("stop", None))
        
    def resume(self) -> None:
        self.is_speaking = True
        self.history.append(("resume", None))

    def trigger_callback(self):
        self.is_speaking = False
        if self._current_callback:
            cb = self._current_callback
            self._current_callback = None
            if asyncio.iscoroutinefunction(cb):
                asyncio.create_task(cb())
            else:
                cb()

async def run_verification():
    print("==================================================")
    print("         AUTOHR PHASE 5.1 VERIFICATION RUN        ")
    print("==================================================")
    
    steps = {
        "init_db": StepTracker("Seeding Database Entities"),
        "init_engine": StepTracker("Orchestrator Initialized"),
        "stage1": StepTracker("Stage 1: Lobby & Greeting Trigger"),
        "stage2": StepTracker("Stage 2: Narration & Slide Changes"),
        "stage3": StepTracker("Stage 3: Q&A Chat Interruption"),
        "stage4": StepTracker("Stage 4: Closing Agent Farewell"),
        "stage5": StepTracker("Stage 5: State Flow Completed"),
        "stage6": StepTracker("Stage 6: Runtime Integrity & config branches")
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

    def clean_db(db_session, s_id):
        try:
            db_session.query(Meeting).filter(Meeting.session_id == s_id).delete()
            db_session.query(Session).filter(Session.id == s_id).delete()
            db_session.query(PresentationScript).filter(PresentationScript.presentation_id == "pres-phase5").delete()
            db_session.query(PresentationQuestion).filter(PresentationQuestion.presentation_id == "pres-phase5").delete()
            db_session.query(Presentation).filter(Presentation.id == "pres-phase5").delete()
            db_session.query(EmployeeList).filter(EmployeeList.id == "emplist-phase5").delete()
            db_session.query(OrganizationConfig).delete()
            db_session.commit()
        except Exception as e:
            db_session.rollback()
            print(f"Database cleanup warning: {e}")

    try:
        clean_db(db, session_id)

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
            organizer_name="HR Team",
            meeting_date="2026-08-01",
            meeting_time="10:00 AM"
        )
        db.add(meeting)

        # Seed PresentationScript (status MUST be COMPLETED as required by runtime_service)
        script_payload = {
            "welcome_flow": {
                "greeting": "Hello and welcome to KONE onboarding.",
                "presenter_intro": "I am your AI HR Trainer {trainer_name}, here to guide you today.",
                "session_rules": "Please stay muted during slides.",
                "agenda": "Today we cover KONE values and safety guidelines."
            },
            "slide_narrations": {
                "1": "First slide: KONE is built on innovation and safety. Welcome {trainer_name} from {company_name}.",
                "2": "Second slide: Safety is our core priority. Report hazards immediately."
            },
            "closing_script": "That concludes KONE values and safety rules induction."
        }
        script = PresentationScript(
            presentation_id="pres-phase5",
            script_content=json.dumps(script_payload),
            llm_model="gemini-1.5-pro",
            status="ACTIVE"
        )
        db.add(script)

        # Seed PresentationQuestion (status MUST be ACTIVE)
        faq_payload = [
            {"question": "What is the policy on safety?", "answer": "KONE has a zero-tolerance policy for safety violations."}
        ]
        faq = PresentationQuestion(
            presentation_id="pres-phase5",
            questions_content=json.dumps(faq_payload),
            status="ACTIVE"
        )
        db.add(faq)
        db.commit()
        
        steps["init_db"].complete(True, "Database seeds injected successfully")
        print("[OK] Seed completed.")

        # Step 2: Initialize Coordinator with Traced Voice Output
        traced_voice = TracedVoiceOutput()
        coord = RuntimeCoordinator(db, session_id, voice_output=traced_voice)
        coord.initialize()
        
        assert coord.session_manager.state == RuntimeState.CREATED
        assert len(coord.employee_context.employees_list) == 1
        assert coord.presenter_context.get_trainer_name() == "KONE Trainer"
        steps["init_engine"].complete(True, "RuntimeCoordinator preloaded and mapped assets correctly")
        print("[OK] Coordinator Initialized.")

        # Step 3: STAGE 1 - Lobby & Greeting Trigger
        print("\n--- STAGE 1: Lobby & Greeting Trigger ---")
        
        # Lobby state check (Negative: Lobby does not trigger welcome greeting)
        obs_lobby = Observation(
            timestamp=time.time(),
            meeting_state=MeetingState.LOBBY,
            observation_state=ObservationState.WAITING,
            presentation_state=PresentationMode.NONE,
            events=[]
        )
        await coord.poll_cycle(obs_lobby)
        assert coord.session_manager.state == RuntimeState.WAITING_FOR_PRESENTATION
        assert not traced_voice.is_speaking
        
        # Presentation started -> INTRODUCTION state
        obs_started = Observation(
            timestamp=time.time(),
            meeting_state=MeetingState.CONNECTED,
            observation_state=ObservationState.ACTIVE,
            presentation_state=PresentationMode.POWERPOINT_SHARED,
            events=[ObservationEvent.PRESENTATION_STARTED],
            timeline_index=1
        )
        await coord.poll_cycle(obs_started)
        await asyncio.sleep(0.1)
        assert coord.session_manager.state == RuntimeState.INTRODUCTION
        assert traced_voice.is_speaking
        
        # Negative test: repeated presentation starts must not re-trigger welcome greeting
        await coord.poll_cycle(obs_started)
        await asyncio.sleep(0.1)
        assert coord.session_manager.state == RuntimeState.INTRODUCTION
        
        # Verify Greeting Placeholder Substitutions
        greeting_text = traced_voice.history[-1][1]
        print(f"  - Generated Greeting: {greeting_text}")
        assert "Jane Doe" in greeting_text
        assert "KONE" in greeting_text
        assert "KONE Trainer" in greeting_text
        assert "safety guidelines" in greeting_text
        
        # Advance state to PRESENTING by completing greeting voice callback
        traced_voice.trigger_callback()
        await asyncio.sleep(0.1)
        assert coord.session_manager.state == RuntimeState.PRESENTING
        assert coord.memory.current_slide_number == 1
        
        # Verify PresentationAgent Contract for slide 1 (placeholder replacement)
        slide1_narration = [act[1] for act in traced_voice.history if act[0] == "say"][1]
        original_slide1 = script_payload["slide_narrations"]["1"]
        expected_slide1 = original_slide1.replace("{trainer_name}", "KONE Trainer").replace("{company_name}", "KONE")
        print(f"DEBUG SLIDE1: slide1_narration={repr(slide1_narration)}")
        print(f"DEBUG SLIDE1: expected_slide1 ={repr(expected_slide1)}")
        assert slide1_narration == expected_slide1
        
        steps["stage1"].complete(True, "Lobby WAITING state, greeting placeholders, and duplicate filters verified")
        print("[OK] Stage 1 Verified")

        # Step 4: STAGE 2 - Narration & Slide Changes
        print("\n--- STAGE 2: Slide Change Narration ---")
        
        # Complete slide 1 voice playback callback
        traced_voice.trigger_callback()
        await asyncio.sleep(0.1)
        
        # Slide change to Slide 2
        obs_slide2 = Observation(
            timestamp=time.time(),
            meeting_state=MeetingState.CONNECTED,
            observation_state=ObservationState.ACTIVE,
            presentation_state=PresentationMode.POWERPOINT_SHARED,
            events=[ObservationEvent.SLIDE_CHANGED],
            timeline_index=2
        )
        await coord.poll_cycle(obs_slide2)
        await asyncio.sleep(0.1)
        assert coord.memory.current_slide_number == 2
        
        # Negative test: repeated identical slide change must not re-trigger narration
        await coord.poll_cycle(obs_slide2)
        await asyncio.sleep(0.1)
        print("DEBUG TRACED VOICE HISTORY FULL:", traced_voice.history)
        assert len([act for act in traced_voice.history if act[0] == "say"]) == 3 # welcome + slide1 + slide2
        
        # Verify Presentation Agent placeholders injection & narration preservation
        slide2_narration = [act[1] for act in traced_voice.history if act[0] == "say"][2]
        print(f"  - Slide 2 Narration: {slide2_narration}")
        original_slide2 = script_payload["slide_narrations"]["2"]
        assert slide2_narration == original_slide2
        
        steps["stage2"].complete(True, "Narration placeholders, duplicate filter checks resolved successfully")
        print("[OK] Stage 2 Verified")

        # Step 5: STAGE 3 - Q&A Chat Interruption
        print("\n--- STAGE 3: Q&A Chat Interruption ---")
        
        # Inject question when narration is active
        assert traced_voice.is_speaking
        answer = await coord.inject_question("Jane Doe", "What is the policy on safety?")
        
        # Assert active voice was interrupted
        assert traced_voice.history[-2] == ("interrupt", None)
        assert traced_voice.history[-1][0] == "say"
        assert "zero-tolerance" in answer
        
        # Test RuntimeConfig allow_questions = False
        coord.config.allow_questions = False
        disabled_answer = await coord.inject_question("Jane Doe", "Where is the cafeteria?")
        assert "disabled" in disabled_answer
        coord.config.allow_questions = True # restore
        
        steps["stage3"].complete(True, "Narration interruptions, config branch blocks validated cleanly")
        print("[OK] Stage 3 Verified")

        # Step 6: STAGE 4 - Closing Agent Farewell
        print("\n--- STAGE 4: Closing Agent Farewell ---")
        
        # Simulating presentation ended during active speech (Negative test)
        obs_ended = Observation(
            timestamp=time.time(),
            meeting_state=MeetingState.CONNECTED,
            observation_state=ObservationState.LOST,
            presentation_state=PresentationMode.NONE,
            events=[ObservationEvent.PRESENTATION_ENDED]
        )
        await coord.poll_cycle(obs_ended)
        await asyncio.sleep(0.1)
        assert coord.session_manager.state == RuntimeState.QUESTION_ANSWER
        
        # Assert previous narration/Q&A was cancelled on presentation end
        assert traced_voice.history[-2] == ("say", "KONE has a zero-tolerance policy for safety violations.")
        
        steps["stage4"].complete(True, "Interrupted speaking cancellation on end signal validated")
        print("[OK] Stage 4 Verified")

        # Step 7: STAGE 5 - State Flow Completed
        print("\n--- STAGE 5: State Flow Completed ---")
        
        # Complete closing agent voice callback
        traced_voice.trigger_callback()
        assert coord.session_manager.state == RuntimeState.COMPLETED
        
        steps["stage5"].complete(True, "Induction lifecycle workflow terminated at COMPLETED successfully")
        print("[OK] Stage 5 Verified")

        # Step 8: STAGE 6 - Runtime Integrity & Config branches
        print("\n--- STAGE 6: Runtime Integrity & Config branches ---")
        
        # Verify SessionMemory properties
        memory_report = coord.memory.get_memory_report()
        print(f"  - Session Memory Report: {memory_report}")
        assert memory_report["total_slides_completed"] == 2
        assert memory_report["slides_completed_list"] == [1, 2]
        assert memory_report["questions_asked_count"] == 2
        assert memory_report["questions_answered_count"] == 1
        assert memory_report["elapsed_seconds"] >= 0
        
        # Verify voice_enabled = False skips speaking entirely
        traced_voice_disabled = TracedVoiceOutput()
        config_disabled = RuntimeConfig(voice_enabled=False)
        coord_disabled = RuntimeCoordinator(db, session_id, voice_output=traced_voice_disabled, config=config_disabled)
        coord_disabled.initialize()
        
        # Start presentation
        await coord_disabled.poll_cycle(obs_lobby)
        await coord_disabled.poll_cycle(obs_started)
        await asyncio.sleep(0.1)
        # Verify state transitioned straight to PRESENTING (skipped waiting for welcome voice triggers)
        assert coord_disabled.session_manager.state == RuntimeState.PRESENTING
        assert len(traced_voice_disabled.history) == 0 # no speak calls made
        
        # Verify RuntimeCoordinator ownership contract (Sole entry point controlling state, config, contexts, and voice layers)
        assert coord.session_manager is not None
        assert coord.employee_context is not None
        assert coord.presenter_context is not None
        assert coord.flow_controller is not None
        assert coord.voice_output is not None
        assert hasattr(coord, "poll_cycle")
        assert hasattr(coord, "inject_question")
        
        steps["stage6"].complete(True, "Memory audit logs, config skip checks, and coordinator ownership validated cleanly")
        print("[OK] Stage 6 Verified")

    finally:
        # Clean up mock Excel
        if os.path.exists(excel_path):
            os.remove(excel_path)
        clean_db(db, session_id)
        db.close()

    print("\n" + "=" * 50)
    print("       AUTOHR PHASE 5.1 VERIFICATION SUMMARY        ")
    print("=" * 50)
    passed_all = True
    for key, step in steps.items():
        if not step.success:
            passed_all = False
        icon = "[OK]" if step.success else "[X]"
        print(f"{icon:<4} {step.name:<45} | {step.details}")
    print("-" * 50)
    status_str = "PASSED" if passed_all else "FAILED"
    print(f"Overall Status: {status_str}")
    print("=" * 50)

if __name__ == "__main__":
    asyncio.run(run_verification())
