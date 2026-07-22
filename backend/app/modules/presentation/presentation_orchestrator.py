import asyncio
import datetime
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session as DBSession
from loguru import logger

from app.db.database import SessionLocal
from app.models.runtime import Runtime
from app.modules.presentation.models import PresentationSession, SlideData, PresentationAction, NarrationBlock
from app.modules.presentation.presentation_memory import PresentationMemory
from app.modules.presentation.presentation_agent import presentation_agent
from app.modules.presentation.narration_engine import narration_engine
from app.modules.presentation.speech_engine import speech_engine
from app.modules.presentation.presentation_events import presentation_events
from app.modules.presentation.presentation_session_service import presentation_session_service
from app.services.event_bus import runtime_event_bus

class PresentationOrchestrator:
    """
    Stage 7 — Presentation Orchestrator
    Central orchestrator coordinating PresentationAgent -> NarrationEngine -> SpeechEngine -> BrowserController -> PresentationMemory.
    Manages state machine transitions from GREETING -> INTRODUCTION -> PRESENTING -> SLIDE_TRANSITION -> SUMMARY -> WAITING_FOR_QA.
    """
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.memory = PresentationMemory(session_id)
        self._is_running: bool = False
        self._is_paused: bool = False
        self.session_data: Optional[PresentationSession] = None

    async def start_presentation(self, db: DBSession) -> bool:
        """
        POST /runtime/{id}/presentation/start
        Triggers full autonomous presentation pipeline.
        """
        if self._is_running:
            logger.warning(f"PresentationOrchestrator | Session {self.session_id} presentation already running.")
            return False

        self.session_data = presentation_session_service.build_presentation_session(db, self.session_id)
        if not self.session_data.slides:
            logger.error(f"PresentationOrchestrator | Session {self.session_id} has no slides to present.")
            return False

        self._is_running = True
        self._is_paused = False
        self.memory.start_session(len(self.session_data.slides))
        self._update_runtime_state("PRESENTATION_INITIALIZING")

        presentation_events.publish_presentation_started(self.session_id, len(self.session_data.slides))

        # Launch background orchestrator loop
        asyncio.create_task(self._run_presentation_pipeline())
        return True

    def pause_presentation(self) -> None:
        self._is_paused = True
        speech_engine.pause()
        self.memory.is_paused = True
        self._update_runtime_state("PAUSED")
        logger.info(f"PresentationOrchestrator | Session {self.session_id} presentation paused.")

    def resume_presentation(self) -> None:
        if self._is_paused:
            self._is_paused = False
            speech_engine.resume()
            self.memory.is_paused = False
            self._update_runtime_state("PRESENTING")
            logger.info(f"PresentationOrchestrator | Session {self.session_id} presentation resumed.")

    def stop_presentation(self) -> None:
        self._is_running = False
        self._is_paused = False
        speech_engine.stop()
        self._update_runtime_state("STOPPED")
        logger.info(f"PresentationOrchestrator | Session {self.session_id} presentation stopped.")

    async def _run_presentation_pipeline(self) -> None:
        try:
            # Item 4: Dynamic Greeting Generation via PresentationAgent
            self._update_runtime_state("GREETING")
            greeting_text = presentation_agent.generate_greeting_and_intro(
                company_name="KONE",
                presenter_name="KONE AutoHR Trainer"
            )
            presentation_events.publish_narration_started(self.session_id, 0, greeting_text)
            
            await speech_engine.speak(NarrationBlock(
                slide_number=0,
                text=greeting_text,
                estimated_duration=4.5
            ))
            presentation_events.publish_narration_completed(self.session_id, 0)

            self._update_runtime_state("INTRODUCTION")
            await asyncio.sleep(1)

            # Slide Narration Loop
            total = len(self.session_data.slides)
            for idx in range(total):
                if not self._is_running:
                    break

                while self._is_paused:
                    await asyncio.sleep(0.5)

                slide: SlideData = self.session_data.slides[idx]
                self.memory.record_slide_visit(slide.slide_number)
                self._update_runtime_state("PRESENTING", current_slide=slide.slide_number)

                presentation_events.publish_slide_started(self.session_id, slide.slide_number, slide.title)

                # Generate intelligence & narration
                narration, action = presentation_agent.generate_slide_presentation(
                    slide=slide,
                    current_index=idx,
                    total_slides=total
                )

                presentation_events.publish_narration_started(self.session_id, slide.slide_number, narration.text)
                self.memory.record_narration(slide.slide_number, narration.text, narration.estimated_duration)

                # Deliver speech via SpeechEngine
                await speech_engine.speak(narration)

                presentation_events.publish_narration_completed(self.session_id, slide.slide_number)
                presentation_events.publish_slide_completed(self.session_id, slide.slide_number)

                # Item 1: Drive Teams Browser Controller to advance slide physically
                if action.action == "ADVANCE_SLIDE" and idx + 1 < total:
                    self._update_runtime_state("SLIDE_TRANSITION", current_slide=slide.slide_number + 1)
                    from app.services.teams_runtime_service import teams_runtime_service
                    advanced = await teams_runtime_service.advance_slide(self.session_id)
                    logger.info(f"PresentationOrchestrator | Advanced Teams browser slide ({slide.slide_number} -> {slide.slide_number + 1}): {advanced}")
                    await asyncio.sleep(1.5)

            # SUMMARY & WAITING_FOR_QA
            if self._is_running:
                self._update_runtime_state("SUMMARY")
                summary_text = "That concludes our core induction presentation. Thank you for your time!"
                await speech_engine.speak(NarrationBlock(
                    slide_number=total,
                    text=summary_text,
                    estimated_duration=3.5
                ))

                self.memory.complete_session()
                presentation_events.publish_presentation_completed(self.session_id, len(self.memory.visited_slides))
                self._update_runtime_state("WAITING_FOR_QA")

        except Exception as e:
            logger.error(f"PresentationOrchestrator | Session {self.session_id} pipeline error: {e}")
            self._update_runtime_state("FAILED")

    def _update_runtime_state(self, state: str, current_slide: Optional[int] = None) -> None:
        with SessionLocal() as db:
            runtime = db.query(Runtime).filter(Runtime.session_id == self.session_id).first()
            if not runtime:
                runtime = Runtime(session_id=self.session_id)
                db.add(runtime)
            runtime.state = state
            if current_slide is not None:
                runtime.current_slide = current_slide
            runtime.last_heartbeat = datetime.datetime.now()
            db.commit()

# Registry of active session orchestrators
_orchestrator_registry: Dict[str, PresentationOrchestrator] = {}

def get_presentation_orchestrator(session_id: str) -> PresentationOrchestrator:
    if session_id not in _orchestrator_registry:
        _orchestrator_registry[session_id] = PresentationOrchestrator(session_id)
    return _orchestrator_registry[session_id]

# Item 5: Deterministic Event Trigger (MeetingJoined -> Auto Start Presentation Pipeline)
def _on_meeting_joined_auto_start(payload: dict) -> None:
    session_id = payload.get("session_id")
    if session_id:
        logger.info(f"PresentationOrchestrator | Event 'MeetingJoined' received for session {session_id}. Auto-starting presentation pipeline...")
        orchestrator = get_presentation_orchestrator(session_id)
        with SessionLocal() as db:
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(orchestrator.start_presentation(db))
            except RuntimeError:
                asyncio.run(orchestrator.start_presentation(db))

runtime_event_bus.subscribe("MeetingJoined", _on_meeting_joined_auto_start)
