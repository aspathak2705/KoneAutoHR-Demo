import asyncio
from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session as DBSession
from loguru import logger

from app.modules.induction_runtime.models.runtime_state import RuntimeState
from app.modules.induction_runtime.config.runtime_config import RuntimeConfig

from app.modules.induction_runtime.orchestrator.session_manager import RuntimeSessionManager
from app.modules.induction_runtime.orchestrator.conversation_orchestrator import ConversationOrchestrator
from app.modules.induction_runtime.context.employee_context_manager import EmployeeContextManager
from app.modules.induction_runtime.context.trainer_context_manager import TrainerContextManager
from app.modules.induction_runtime.context.session_memory import SessionMemory
from app.modules.induction_runtime.narrator.voice_output_interface import VoiceOutputInterface, DefaultVoiceOutput
from app.modules.induction_runtime.narrator.presentation_flow_controller import PresentationFlowController

from app.modules.induction_runtime.agents.greeting_agent import greeting_agent
from app.modules.induction_runtime.agents.presentation_agent import presentation_agent
from app.modules.induction_runtime.agents.qa_agent import qa_agent

from app.modules.presentation_observer.models.observation import Observation
from app.modules.presentation_observer.models.observation_state import ObservationState
from app.modules.presentation_observer.models.observation_event import ObservationEvent

class RuntimeCoordinator:
    """
    Master Orchestrator / Coordinator.
    CRITICAL RULE: The RuntimeCoordinator is the only module allowed to invoke multiple runtime components during a session.
    """
    def __init__(
        self, 
        db: Optional[DBSession], 
        session_id: str, 
        voice_output: Optional[VoiceOutputInterface] = None,
        config: Optional[RuntimeConfig] = None
    ):
        self.session_id = session_id
        self.voice_output = voice_output or DefaultVoiceOutput(session_id)
        self.config = config or RuntimeConfig()
        
        # Instantiate subcomponents
        self.session_manager = RuntimeSessionManager()
        self.conversation_orchestrator = ConversationOrchestrator()
        self.employee_context = EmployeeContextManager()
        self.presenter_context = TrainerContextManager()
        self.memory = SessionMemory()
        self.flow_controller = PresentationFlowController(self.voice_output)

        # Cache variables
        self.script_opening: Dict[str, Any] = {}
        self.script_slides: List[Dict[str, Any]] = []
        self.script_closing: Dict[str, Any] = {}
        self.faq_records: List[Dict[str, Any]] = []

        # Interruption tracking
        self._current_narration_text: Optional[str] = None

    def initialize(self) -> None:
        """
        Preloads session records, script payload, employee registers, and policies from database.
        """
        logger.info(f"RuntimeCoordinator | Initializing orchestration context for Session: {self.session_id}...")
        
        # Load from database using existing RuntimeService context builders
        from app.services.runtime_service import runtime_service
        from app.db.database import SessionLocal
        try:
            with SessionLocal() as db:
                ctx = runtime_service.get_runtime_context(db, self.session_id)
            
            # 1. Load employee register files
            self.employee_context.employees_list = ctx.get("employees", [])
            logger.info(f"RuntimeCoordinator | Standardized {len(self.employee_context.employees_list)} employee context records.")

            # 2. Load presenter configurations
            self.presenter_context.profile = ctx.get("persona", {})
            logger.info(f"RuntimeCoordinator | Standardized Trainer Context: {self.presenter_context.get_profile_summary()}")

            # 3. Load presentation script
            script_data = ctx.get("script", {})
            self.script_opening = script_data.get("welcome_flow") or {}
            raw_narrations = script_data.get("slide_narrations") or {}
            
            # Map slide narrations to schema structure
            self.script_slides = []
            for num_str, narration in raw_narrations.items():
                self.script_slides.append({
                    "slide_number": int(num_str),
                    "title": f"Slide {num_str}",
                    "narration": narration
                })
            self.flow_controller.load_presentation_script(self.script_slides)

            # 4. Load closing scripts
            self.script_closing = {
                "summary": script_data.get("closing_script") or "That concludes our onboarding session.",
                "next_steps": "Please complete your training tasks.",
                "farewell": "Thank you and welcome aboard!"
            }

            # 5. Load FAQ records
            self.faq_records = ctx.get("faq", [])
            logger.info(f"RuntimeCoordinator | Loaded {len(self.faq_records)} policy FAQs.")
        except Exception as e:
            logger.error(f"RuntimeCoordinator | Context preloading failed: {e}")
            raise

    async def poll_cycle(self, observation: Observation) -> None:
        """
        Main execution loop step. Driven by updates from the Presentation Observer.
        """
        logger.debug(f"RuntimeCoordinator | Polling cycle | Observation State: {observation.observation_state} | Active State: {self.session_manager.state}")

        # Transition 1: Lobby -> Waiting for Presentation Started
        if observation.observation_state == ObservationState.WAITING:
            if self.session_manager.state == RuntimeState.CREATED:
                self.session_manager.transition_to(RuntimeState.WAITING_FOR_PRESENTATION)

        # Transition 2: Presentation starts -> INTRODUCTION
        if ObservationEvent.PRESENTATION_STARTED in observation.events:
            if self.session_manager.state in [RuntimeState.CREATED, RuntimeState.WAITING_FOR_PRESENTATION]:
                self.session_manager.transition_to(RuntimeState.INTRODUCTION)
                # Start Greeting Agent welcome flow
                asyncio.create_task(self._run_greeting_flow())
                return

        # Transition 3: Slide Change detected -> PRESENTING
        if ObservationEvent.SLIDE_CHANGED in observation.events:
            if self.session_manager.state == RuntimeState.PRESENTING:
                # Slide index changed
                slide_num = observation.timeline_index
                if slide_num != self.memory.current_slide_number:
                    self.memory.record_slide_reached(slide_num, f"Slide {slide_num}")
                    
                    # Interrupt active voice narration
                    if self.config.voice_enabled:
                        self.voice_output.interrupt()
                    
                    # Speak new slide narration
                    asyncio.create_task(self._speak_slide_narration(slide_num))

        # Transition 4: Presentation ends -> QUESTION_ANSWER / COMPLETED
        if ObservationEvent.PRESENTATION_ENDED in observation.events:
            if self.session_manager.is_active():
                self.session_manager.transition_to(RuntimeState.QUESTION_ANSWER)
                
                # Run closing agent greeting farewell
                asyncio.create_task(self._run_closing_flow())

    async def inject_question(self, speaker: str, question_text: str) -> str:
        """
        Simulates chat question injection. Interrupts current narration and answers.
        """
        logger.info(f"RuntimeCoordinator | Question received from {speaker}: '{question_text}'")
        self.memory.record_question(speaker, question_text)

        if not self.config.allow_questions:
            logger.warning("RuntimeCoordinator | Question injection rejected: allow_questions is disabled.")
            return "Questions are currently disabled."

        # Interrupt current narration if voice is active
        if self.config.voice_enabled:
            self.voice_output.interrupt()
        
        # Call QAAgent to generate answer
        answer = await qa_agent.answer_question(question_text, self.faq_records, self.presenter_context.profile)
        
        # Save to memory and play back answer
        self.memory.record_answer(question_text, answer)
        
        # Persist message history in database
        from app.db.database import SessionLocal
        from app.models.runtime_message import RuntimeMessage
        try:
            with SessionLocal() as db:
                emp_msg = RuntimeMessage(
                    session_id=self.session_id,
                    speaker_name=speaker,
                    message_text=question_text
                )
                db.add(emp_msg)
                ai_msg = RuntimeMessage(
                    session_id=self.session_id,
                    speaker_name=self.presenter_context.profile.get("ai_trainer_name", "KONE Trainer"),
                    message_text=answer
                )
                db.add(ai_msg)
                db.commit()
        except Exception as e:
            logger.error(f"RuntimeCoordinator | Failed to persist message to database: {e}")

        # Speak the answer if allowed
        if self.config.voice_enabled:
            self.voice_output.say(answer)
        return answer

    async def _run_greeting_flow(self) -> None:
        """
        Executes Greeting Agent welcome script narration.
        """
        primary_emp = self.employee_context.get_primary_inductee() or {}
        welcome_text = await greeting_agent.generate_welcome(
            primary_emp,
            self.presenter_context.profile,
            self.script_opening
        )
        
        def on_welcome_complete():
            logger.info("RuntimeCoordinator | Welcome greeting completed. Advancing to slide presentation.")
            self.session_manager.transition_to(RuntimeState.PRESENTING)
            
            # Start narration of slide 1
            self.memory.record_slide_reached(1, "Slide 1")
            asyncio.create_task(self._speak_slide_narration(1))

        if self.config.voice_enabled:
            self.voice_output.say(welcome_text, on_welcome_complete)
        else:
            on_welcome_complete()

    async def _speak_slide_narration(self, slide_num: int) -> None:
        """
        Formats slide narration using PresentationAgent and speaks via Flow Controller.
        """
        slide = self.flow_controller.get_slide_by_number(slide_num)
        if not slide:
            return
            
        raw_narration = slide.get("narration", "")
        # Format raw narration
        spoken_text = await presentation_agent.format_narration(
            slide.get("title", f"Slide {slide_num}"),
            raw_narration,
            self.presenter_context.profile
        )
        
        # Update slide narration in-place to carry the resolved placeholders
        slide["narration"] = spoken_text
        
        self._current_narration_text = spoken_text
        if self.config.voice_enabled:
            self.flow_controller.trigger_slide_narration(slide_num, lambda: logger.info(f"Finished slide {slide_num} narration."))
        else:
            logger.info(f"RuntimeCoordinator | Speaking disabled. Bypassed narration: {spoken_text}")

    async def _run_closing_flow(self) -> None:
        """
        Executes Closing Agent farewell.
        """
        farewell = (
            f"{self.script_closing.get('summary', '')} "
            f"{self.script_closing.get('next_steps', '')} "
            f"{self.script_closing.get('farewell', '')}"
        )
        
        def on_farewell_complete():
            logger.info("RuntimeCoordinator | Farewell narration completed. Ending session.")
            self.session_manager.transition_to(RuntimeState.COMPLETED)

        if self.config.voice_enabled:
            self.voice_output.say(farewell, on_farewell_complete)
        else:
            on_farewell_complete()
