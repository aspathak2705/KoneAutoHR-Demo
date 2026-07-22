import asyncio
import datetime
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session as DBSession
from loguru import logger

from app.db.database import SessionLocal
from app.models.runtime import Runtime
from app.modules.presentation.session_script_models import SessionScript, ScriptStep, QAContext
from app.modules.presentation.session_script_generator import session_script_generator
from app.modules.session.session_memory import SessionMemory
from app.modules.session.runtime_orchestrator import RuntimeOrchestrator
from app.modules.presentation.session_events import session_events
from app.modules.presentation.speech_engine import speech_engine
from app.services.attendance_service import attendance_service
from app.modules.presentation.handlers import (
    WaitForParticipantsHandler,
    SpokenTextHandler,
    PresentationHandler,
    WaitForQuestionsHandler,
    ClosingHandler,
    PlayVideoHandler,
    ShowImageHandler,
    PollHandler
)

class SessionInterpreter:
    """
    Module 4 & 7 — Session Interpreter & Runtime State Machine (V4.0)
    Orchestrates onboarding steps using RuntimeOrchestrator.
    Deterministic execution. Zero LLM calls during runtime!
    """
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.memory = SessionMemory(session_id)
        self.orchestrator = RuntimeOrchestrator(session_id)
        self._is_running: bool = False
        self._is_paused: bool = False
        self.script: Optional[SessionScript] = None

        # Handlers
        self.wait_participants_handler = WaitForParticipantsHandler()
        self.greeting_handler = SpokenTextHandler("GREETING")
        self.intro_handler = SpokenTextHandler("INTRODUCTION")
        self.audio_check_handler = SpokenTextHandler("AUDIO_CHECK")
        self.rules_handler = SpokenTextHandler("SESSION_RULES")
        self.icebreaker_handler = SpokenTextHandler("ICE_BREAKER")
        self.pres_section_handler = SpokenTextHandler("PRESENTATION_SECTION")
        self.presentation_handler = PresentationHandler()
        self.understanding_handler = SpokenTextHandler("UNDERSTANDING_CHECK")
        self.summary_handler = SpokenTextHandler("SUMMARY")
        self.qa_handler = WaitForQuestionsHandler()
        self.closing_handler = ClosingHandler()
        self.play_video_handler = PlayVideoHandler()
        self.show_image_handler = ShowImageHandler()
        self.poll_handler = PollHandler()

    async def start_session(self, db: DBSession, start_from_step: Optional[int] = None) -> bool:
        """
        Starts or resumes session cleanly from start_from_step.
        """
        if self._is_running:
            logger.warning(f"SessionInterpreter | Session {self.session_id} already running.")
            return False

        self.script = session_script_generator.generate_session_script(db, self.session_id)
        if not self.script or not self.script.steps:
            logger.error(f"SessionInterpreter | Failed to load script for {self.session_id}.")
            return False

        self._is_running = True
        self._is_paused = False
        self.memory.start_session(len(self.script.steps))
        
        resume_step = start_from_step or 1
        self._update_runtime_state("INITIALIZING")
        session_events.publish(self.session_id, "SessionStarted", {"total_steps": len(self.script.steps), "resume_step": resume_step})

        # Initialize Supervisor, load assets, join meeting, verify sharing
        from app.models.meeting import Meeting
        meeting = db.query(Meeting).filter(Meeting.session_id == self.session_id).first()
        teams_url = meeting.teams_url if meeting else ""
        
        # Resolve from presentation file (Mock/Local mode fallback)
        asset_id = self.script.session_id
        
        await self.orchestrator.initialize_and_join(db, teams_url, asset_id, guest_name=self.script.presenter_name)

        asyncio.create_task(self._run_interpreter_loop(start_from_step=resume_step))
        return True

    def get_qa_context(self) -> QAContext:
        exec_ctx = self.memory.get_execution_context()
        attendees = attendance_service.get_attendance(self.session_id)
        
        return QAContext(
            session_id=self.session_id,
            memory=exec_ctx.dict(),
            attendance=attendees if isinstance(attendees, dict) else {},
            presentation_progress={
                "current_slide": self.orchestrator.ctx.current_slide,
                "is_slideshow_active": self.orchestrator.pres_sup.adapter._process is not None
            },
            browser_session_active=True,
            knowledge_sources={"company": "KONE", "faqs_loaded": True}
        )

    def pause_session(self) -> None:
        self._is_paused = True
        speech_engine.pause()
        self.memory.is_paused = True
        self._update_runtime_state("PAUSED")
        logger.info(f"SessionInterpreter | Session {self.session_id} paused.")

    def resume_session(self) -> None:
        if self._is_paused:
            self._is_paused = False
            speech_engine.resume()
            self.memory.is_paused = False
            self._update_runtime_state("PRESENTING")
            logger.info(f"SessionInterpreter | Session {self.session_id} resumed.")

    def stop_session(self) -> None:
        self._is_running = False
        self._is_paused = False
        speech_engine.stop()
        self._update_runtime_state("STOPPED")
        logger.info(f"SessionInterpreter | Session {self.session_id} stopped.")

    async def _run_interpreter_loop(self, start_from_step: int = 1) -> None:
        try:
            for step in self.script.steps:
                if step.step_id < start_from_step:
                    continue
                if not self._is_running:
                    break

                while self._is_paused:
                    await asyncio.sleep(0.5)

                self.memory.record_step_start(step.step_id, step.type)
                self._update_runtime_state(step.type)

                if step.type == "WAIT_FOR_PARTICIPANTS":
                    await self.wait_participants_handler.execute(step, self.session_id)
                    session_events.publish(self.session_id, "ParticipantsReady")

                elif step.type == "GREETING":
                    # Speak using orchestrator
                    await self.orchestrator.speak(" ".join(step.speech or []), slide_num=0)
                    session_events.publish(self.session_id, "GreetingCompleted")

                elif step.type == "INTRODUCTION":
                    await self.orchestrator.speak(" ".join(step.speech or []), slide_num=0)
                    session_events.publish(self.session_id, "IntroductionCompleted")

                elif step.type == "AUDIO_CHECK":
                    await self.orchestrator.speak(" ".join(step.speech or []), slide_num=0)
                    session_events.publish(self.session_id, "AudioCheckCompleted")

                elif step.type == "SESSION_RULES":
                    await self.orchestrator.speak(" ".join(step.speech or []), slide_num=0)

                elif step.type == "ICE_BREAKER":
                    await self.orchestrator.speak(" ".join(step.speech or []), slide_num=0)
                    session_events.publish(self.session_id, "IceBreakerCompleted")

                elif step.type == "PRESENTATION_SECTION":
                    await self.orchestrator.speak(" ".join(step.speech or []), slide_num=step.slide_number or 0)
                    session_events.publish(self.session_id, "PresentationSectionStarted", {"section_title": step.section_title})

                elif step.type == "SHOW_SLIDE":
                    # Navigate slide via Orchestrator
                    await self.orchestrator.navigate_slide(step.slide_number or 1)
                    # Narrate before
                    if step.before:
                        await self.orchestrator.speak(" ".join(step.before), slide_num=step.slide_number or 1)
                    # Narrate during
                    if step.during:
                        await self.orchestrator.speak(" ".join(step.during), slide_num=step.slide_number or 1)
                    # Narrate after
                    if step.after:
                        await self.orchestrator.speak(" ".join(step.after), slide_num=step.slide_number or 1)

                    session_events.publish(self.session_id, "SlidePresented", {"slide_id": step.slide_id, "slide_number": step.slide_number})

                elif step.type == "PLAY_VIDEO":
                    await self.orchestrator.play_video(step.asset_url or "", step.duration or 10)

                elif step.type == "SHOW_IMAGE":
                    await self.show_image_handler.execute(step, self.session_id)

                elif step.type == "POLL":
                    await self.poll_handler.execute(step, self.session_id)

                elif step.type == "UNDERSTANDING_CHECK":
                    await self.orchestrator.speak(" ".join(step.speech or []), slide_num=step.slide_number or 0)
                    session_events.publish(self.session_id, "UnderstandingChecked")

                elif step.type == "SUMMARY":
                    await self.orchestrator.speak(" ".join(step.speech or []), slide_num=step.slide_number or 0)
                    session_events.publish(self.session_id, "PresentationCompleted")

                elif step.type == "WAIT_FOR_QUESTIONS":
                    await self.qa_handler.execute(step, self.session_id)
                    session_events.publish(self.session_id, "WaitingForQuestions")
                    self._update_runtime_state("WAITING_FOR_QA")

                elif step.type == "CLOSING":
                    await self.orchestrator.speak(" ".join(step.speech or []), slide_num=100)
                    session_events.publish(self.session_id, "ClosingCompleted")

                elif step.type == "LEAVE_MEETING":
                    session_events.publish(self.session_id, "MeetingLeft")
                    await self.orchestrator.shutdown()
                    break

                self.memory.record_step_complete(step.step_id)
                await asyncio.sleep(1)

            logger.info(f"SessionInterpreter | Session {self.session_id} completed successfully.")
            self._update_runtime_state("COMPLETED")

        except Exception as e:
            logger.error(f"SessionInterpreter | Session {self.session_id} execution error: {e}")
            self._update_runtime_state("FAILED")
            await self.orchestrator.shutdown()

    def _update_runtime_state(self, state: str) -> None:
        with SessionLocal() as db:
            runtime = db.query(Runtime).filter(Runtime.session_id == self.session_id).first()
            if not runtime:
                runtime = Runtime(session_id=self.session_id)
                db.add(runtime)
            runtime.state = state
            runtime.last_heartbeat = datetime.datetime.now()
            db.commit()

# Registry of active session interpreters
_interpreter_registry: Dict[str, SessionInterpreter] = {}

def get_session_interpreter(session_id: str) -> SessionInterpreter:
    if session_id not in _interpreter_registry:
        _interpreter_registry[session_id] = SessionInterpreter(session_id)
    return _interpreter_registry[session_id]

# Auto-trigger on Teams MeetingJoined event
def _on_meeting_joined_auto_start_session(payload: dict) -> None:
    session_id = payload.get("session_id")
    if session_id:
        logger.info(f"SessionInterpreter | Event 'MeetingJoined' received for session {session_id}. Auto-starting HR induction session...")
        interpreter = get_session_interpreter(session_id)
        with SessionLocal() as db:
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(interpreter.start_session(db))
            except RuntimeError:
                asyncio.run(interpreter.start_session(db))

from app.services.event_bus import runtime_event_bus
runtime_event_bus.subscribe("MeetingJoined", _on_meeting_joined_auto_start_session)
