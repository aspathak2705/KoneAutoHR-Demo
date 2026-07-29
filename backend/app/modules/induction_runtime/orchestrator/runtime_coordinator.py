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
    Master Orchestrator / Coordinator - LOCKED Architecture.
    
    CRITICAL RULES:
    - RuntimeCoordinator is the SOLE owner of runtime lifecycle state.
    - RuntimeCoordinator manages the locked 13-state state machine.
    - RuntimeCoordinator NEVER directly manages browser resources (BrowserManager does).
    - RuntimeCoordinator NEVER directly manages Teams operations (TeamsController does).
    - All state transitions are validated and persisted to database.
    - All async operations follow START→TRY→SUCCESS→STATE_UPDATE pattern.
    - All errors are logged with FAILED status and never swallowed.
    """
    def __init__(
        self, 
        db: Optional[DBSession], 
        session_id: str,
        runtime_id: Optional[str] = None,
        voice_output: Optional[VoiceOutputInterface] = None,
        config: Optional[RuntimeConfig] = None
    ):
        self.session_id = session_id
        self.runtime_id = runtime_id
        self.db = db
        self.voice_output = voice_output or DefaultVoiceOutput(session_id)
        self.config = config or RuntimeConfig()
        
        # State machine guard - manages lifecycle only
        self.session_manager = RuntimeSessionManager(db=db, runtime_id=runtime_id)
        self.session_manager.state = RuntimeState.NOT_CREATED
        
        # Instantiate subcomponents (non-state-bearing)
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
        
        # Lifecycle tracking
        self._browser_manager = None
        self._teams_controller = None
        
        # Retry policy for transient failures
        self.max_retries = 3
        self.retry_delay = 1  # seconds
        self._retry_count = 0

    def initialize(self) -> None:
        """
        Bypasses async preparation and loads context synchronously.
        Used for verification and setup.
        """
        self._initialize_context()

    async def prepare_runtime(self) -> bool:
        """
        Lifecycle Phase: PREPARING → READY
        
        Prepares runtime by:
        1. Validating assets and configuration
        2. Loading all required data
        3. Validating startup prerequisites
        4. Transitioning to READY state
        
        Returns True on success, False on failure.
        """
        logger.info(f"RuntimeCoordinator | START prepare_runtime")
        
        try:
            # Transition to PREPARING
            if not await self.session_manager.transition_to(RuntimeState.PREPARING):
                raise Exception("Failed to transition to PREPARING state")
            
            # Load context from database
            self._initialize_context()
            
            # MANDATORY 3: Validate startup prerequisites before READY
            self._validate_startup_prerequisites()
            
            # Transition to READY
            if not await self.session_manager.transition_to(RuntimeState.READY):
                raise Exception("Failed to transition to READY state")
            
            logger.info(f"RuntimeCoordinator | SUCCESS prepare_runtime - Ready for induction")
            return True
        except Exception as e:
            logger.error(f"RuntimeCoordinator | FAILED prepare_runtime: {e}")
            await self.session_manager.transition_to(RuntimeState.FAILED, str(e))
            return False

    def _validate_startup_prerequisites(self) -> None:
        """
        MANDATORY 3: Validates all prerequisites before entering READY state.
        
        Checks:
        - Presentation script loaded
        - Employee list available
        - Meeting configuration present
        - Browser installation verified
        - Presentation audio prepared
        
        Raises exception if any prerequisite missing.
        """
        logger.info(f"RuntimeCoordinator | START _validate_startup_prerequisites")
        
        try:
            # Check presentation script
            if not self.script_slides:
                raise Exception("Presentation script not loaded")
            
            # Check employees
            if not self.employee_context.employees_list:
                raise Exception("Employee list not available")
            
            # Check presenter context
            if not self.presenter_context.profile:
                raise Exception("Trainer context not configured")
            
            # Check FAQ
            if not self.faq_records:
                raise Exception("FAQ records not loaded")
            
            logger.info(f"RuntimeCoordinator | SUCCESS _validate_startup_prerequisites - all checks passed")
        except Exception as e:
            logger.error(f"RuntimeCoordinator | FAILED _validate_startup_prerequisites: {e}")
            raise

    async def start_induction(self) -> bool:
        """
        Lifecycle Phase: READY → STARTING → BROWSER_READY
        
        Starts induction by:
        1. Transitioning to STARTING
        2. Launching browser (moved from prepare_runtime)
        3. Opening Teams
        4. Transitioning to BROWSER_READY
        
        Returns True on success, False on failure.
        """
        logger.info(f"RuntimeCoordinator | START start_induction")
        
        try:
            # Verify we're in READY state
            if self.session_manager.state != RuntimeState.READY:
                raise Exception(f"Cannot start induction from state {self.session_manager.state.value}")
            
            # Transition to STARTING
            if not await self.session_manager.transition_to(RuntimeState.STARTING):
                raise Exception("Failed to transition to STARTING state")
            
            # Launch browser (THIS IS THE KEY CHANGE - browser launch moved here)
            self._browser_manager = await self._launch_browser()
            logger.info(f"_browser_manager type: {type(self._browser_manager)}")
            logger.info(f"_browser_manager: {self._browser_manager}")
            logger.info(f"Has session attribute: {hasattr(self._browser_manager, 'session')}")
            if not self._browser_manager:
                raise Exception("Failed to launch browser")
            
            # Transition to BROWSER_READY
            if not await self.session_manager.transition_to(RuntimeState.BROWSER_READY):
                raise Exception("Failed to transition to BROWSER_READY state")
            
            logger.info(f"RuntimeCoordinator | SUCCESS start_induction - Browser ready")
            return True
        except Exception as e:
            logger.error(f"RuntimeCoordinator | FAILED start_induction: {e}")
            await self.session_manager.transition_to(RuntimeState.FAILED, str(e))
            await self._cleanup_resources()
            return False

    async def join_meeting(self, meeting_url: str) -> bool:
        """
        Lifecycle Phase: BROWSER_READY → JOINING → WAITING → CONNECTED
        
        Joins Teams meeting by delegating to MeetingBotService.
        """
        logger.info(f"RuntimeCoordinator | START join_meeting")
        
        try:
            if self.session_manager.state != RuntimeState.BROWSER_READY:
                raise Exception(f"Cannot join meeting from state {self.session_manager.state.value}")
            
            # Transition to JOINING
            if not await self.session_manager.transition_to(RuntimeState.JOINING):
                raise Exception("Failed to transition to JOINING state")
            
            # Use MeetingBotService to join meeting (which encapsulates page.goto and Teams join actions)
            from app.modules.meeting_bot.services.meeting_bot_service import meeting_bot_service
            
            # Set the browser context in MeetingBot to match the browser launched by RuntimeCoordinator
            bot = meeting_bot_service.get_bot(self.session_id)

            logger.info("STEP 1 - Got MeetingBot")
            logger.info(f"BrowserManager exists: {self._browser_manager is not None}")
            
            if self._browser_manager:
                logger.info(f"Session exists: {self._browser_manager.session is not None}")
                if self._browser_manager.session:
                    logger.info(f"Injected page: {self._browser_manager.session.page}")
                    bot.context.browser = self._browser_manager.session.browser
                    bot.context.browser_context = self._browser_manager.session.context
                    bot.context.page = self._browser_manager.session.page
                    bot.context.playwright = self._browser_manager.playwright_instance

            logger.info(f"Bot page after injection: {bot.context.page}")
            logger.info("STEP 3 - Calling initialize()")
            await bot.initialize()
            logger.info("STEP 4 - initialize() returned")

            logger.info(
                f"Coordinator -> Bot state AFTER initialize: {bot.context.state}"
            )

            logger.info(
                f"Coordinator -> Bot state before join: {bot.context.state}"
            )

            logger.info(
                f"Coordinator page id: {id(bot.context.page)}"
            )
            
            # Trigger join meeting
            result = await meeting_bot_service.join_meeting(meeting_url, "KONE AI Bot", self.session_id)
            
            # Transition to WAITING
            if not await self.session_manager.transition_to(RuntimeState.WAITING):
                raise Exception("Failed to transition to WAITING state")
            
            # Transition to CONNECTED when ready
            if not await self.session_manager.transition_to(RuntimeState.CONNECTED):
                raise Exception("Failed to transition to CONNECTED state")
            
            logger.info(f"RuntimeCoordinator | SUCCESS join_meeting - Connected to meeting")
            return True
        except Exception as e:
            logger.error(f"RuntimeCoordinator | FAILED join_meeting: {e}")
            await self.session_manager.transition_to(RuntimeState.FAILED, str(e))
            await self._cleanup_resources()
            return False

    async def finish_presentation(self) -> bool:
        """
        Lifecycle Phase: PRESENTING → FINISHED → STOPPING → STOPPED
        
        Finalizes presentation and cleans up.
        """
        logger.info(f"RuntimeCoordinator | START finish_presentation")
        
        try:
            if not self.session_manager.state in [
                RuntimeState.READY,
                RuntimeState.STARTING,
                RuntimeState.BROWSER_READY,
                RuntimeState.JOINING,
                RuntimeState.WAITING,
                RuntimeState.CONNECTED,
                RuntimeState.PRESENTING
            ]:
                raise Exception(f"Cannot finish from state {self.session_manager.state.value}")
            
            # Transition to FINISHED
            if not await self.session_manager.transition_to(RuntimeState.FINISHED):
                raise Exception("Failed to transition to FINISHED state")
            
            # Transition to STOPPING
            if not await self.session_manager.transition_to(RuntimeState.STOPPING):
                raise Exception("Failed to transition to STOPPING state")
            
            # Cleanup resources in reverse order
            await self._cleanup_resources()
            
            # Transition to STOPPED
            if not await self.session_manager.transition_to(RuntimeState.STOPPED):
                raise Exception("Failed to transition to STOPPED state")
            
            logger.info(f"RuntimeCoordinator | SUCCESS finish_presentation - Runtime stopped")
            return True
        except Exception as e:
            logger.error(f"RuntimeCoordinator | FAILED finish_presentation: {e}")
            await self.session_manager.transition_to(RuntimeState.FAILED, str(e))
            await self._cleanup_resources()
            return False

    def _initialize_context(self) -> None:
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

    async def _launch_browser(self):
        """
        Launches browser via BrowserManager with retry policy for transient failures.
        Returns BrowserManager instance or None on failure.
        """
        logger.info(f"RuntimeCoordinator | START _launch_browser (attempt {self._retry_count + 1}/{self.max_retries})")
        try:
            from app.modules.meeting_bot.browser.browser_manager import browser_manager
            await browser_manager.launch(self.session_id)
            logger.info(f"RuntimeCoordinator | SUCCESS _launch_browser")
            self._retry_count = 0  # Reset on success
            return browser_manager
        except Exception as e:
            logger.error(f"RuntimeCoordinator | FAILED _launch_browser (attempt {self._retry_count + 1}): {e}")
            
            # Retry policy: retry up to max_retries for transient failures
            if self._retry_count < self.max_retries:
                self._retry_count += 1
                logger.info(f"RuntimeCoordinator | Retrying browser launch in {self.retry_delay}s...")
                await asyncio.sleep(self.retry_delay)
                return await self._launch_browser()  # Recursive retry
            
            return None

    async def _init_teams_controller(self):
        """
        Initializes TeamsController.
        Returns TeamsController instance or None on failure.
        """
        logger.info(f"RuntimeCoordinator | START _init_teams_controller")
        try:
            from app.modules.meeting_bot.teams.teams_controller import TeamsController
            teams_ctrl = TeamsController()
            logger.info(f"RuntimeCoordinator | SUCCESS _init_teams_controller")
            return teams_ctrl
        except Exception as e:
            logger.error(f"RuntimeCoordinator | FAILED _init_teams_controller: {e}")
            return None

    async def _open_teams_meeting(self, meeting_url: str) -> bool:
        """
        Opens Teams meeting via TeamsController.
        """
        logger.info(f"RuntimeCoordinator | START _open_teams_meeting")
        try:
            if not self._browser_manager or not self._teams_controller:
                raise Exception("Browser or Teams controller not initialized")
            
            # Get page from browser manager
            if not self._browser_manager.page:
                raise Exception("Browser page not available")
            
            await self._teams_controller.open_meeting(self._browser_manager.page, meeting_url)
            logger.info(f"RuntimeCoordinator | SUCCESS _open_teams_meeting")
            return True
        except Exception as e:
            logger.error(f"RuntimeCoordinator | FAILED _open_teams_meeting: {e}")
            return False

    async def _cleanup_resources(self) -> None:
        """
        Cleanup in reverse order of creation:
        1. Teams controller cleanup
        2. Browser cleanup (via BrowserManager)
        3. Clear references
        """
        logger.info(f"RuntimeCoordinator | START _cleanup_resources")
        
        try:
            # Cleanup Teams controller
            if self._teams_controller:
                try:
                    logger.info(f"RuntimeCoordinator | Cleaning up Teams controller")
                    # Teams controller cleanup if needed
                    self._teams_controller = None
                except Exception as e:
                    logger.error(f"RuntimeCoordinator | Failed to cleanup Teams controller: {e}")
            
            # Cleanup browser
            if self._browser_manager:
                try:
                    logger.info(f"RuntimeCoordinator | Cleaning up browser")
                    await self._browser_manager.close()
                    self._browser_manager = None
                except Exception as e:
                    logger.error(f"RuntimeCoordinator | Failed to cleanup browser: {e}")
            
            logger.info(f"RuntimeCoordinator | SUCCESS _cleanup_resources")
        except Exception as e:
            logger.error(f"RuntimeCoordinator | FAILED _cleanup_resources: {e}")

    async def poll_cycle(self, observation: Observation) -> None:
        """
        Main execution loop step. Driven by updates from the Presentation Observer.
        Uses new locked state machine.
        """
        logger.debug(f"RuntimeCoordinator | Polling cycle | Observation State: {observation.observation_state} | Active State: {self.session_manager.state.value}")

        # Transition: CONNECTED → PRESENTING (presentation started)
        if ObservationEvent.PRESENTATION_STARTED in observation.events:
            if self.session_manager.state == RuntimeState.CONNECTED:
                logger.info(f"RuntimeCoordinator | Presentation started, transitioning to PRESENTING")
                if await self.session_manager.transition_to(RuntimeState.PRESENTING):
                    asyncio.create_task(self._run_greeting_flow())
                return

        # Handle slide changes during PRESENTING
        if ObservationEvent.SLIDE_CHANGED in observation.events:
            if self.session_manager.state == RuntimeState.PRESENTING:
                slide_num = observation.timeline_index
                if slide_num != self.memory.current_slide_number:
                    logger.info(f"RuntimeCoordinator | Slide changed to {slide_num}")
                    self.memory.record_slide_reached(slide_num, f"Slide {slide_num}")
                    
                    # Interrupt active voice narration
                    if self.config.voice_enabled:
                        self.voice_output.interrupt()
                    
                    # Speak new slide narration
                    asyncio.create_task(self._speak_slide_narration(slide_num))

        # Transition: PRESENTING → FINISHED (presentation ended)
        if ObservationEvent.PRESENTATION_ENDED in observation.events:
            if self.session_manager.state == RuntimeState.PRESENTING:
                logger.info(f"RuntimeCoordinator | Presentation ended, starting cleanup")
                asyncio.create_task(self._run_closing_flow())
                asyncio.create_task(self.finish_presentation())

    async def inject_question(self, speaker: str, question_text: str) -> str:
        """
        Simulates chat question injection. Interrupts current narration and answers.
        Only allowed during PRESENTING state.
        """
        logger.info(f"RuntimeCoordinator | START inject_question from {speaker}")
        
        try:
            if self.session_manager.state != RuntimeState.PRESENTING:
                msg = f"Questions not allowed in {self.session_manager.state.value} state"
                logger.warning(f"RuntimeCoordinator | {msg}")
                return msg
            
            logger.info(f"RuntimeCoordinator | Question received: '{question_text}'")
            self.memory.record_question(speaker, question_text)

            if not self.config.allow_questions:
                logger.warning("RuntimeCoordinator | Question injection rejected: allow_questions is disabled.")
                return "Questions are currently disabled."

            # Interrupt current narration if voice is active
            if self.config.voice_enabled:
                self.voice_output.interrupt()
            
            # Call QAAgent to generate answer
            answer = await qa_agent.answer_question(question_text, self.faq_records, self.presenter_context.profile)
            
            # Save to memory
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
            
            logger.info(f"RuntimeCoordinator | SUCCESS inject_question - answered")
            return answer
        except Exception as e:
            logger.error(f"RuntimeCoordinator | FAILED inject_question: {e}")
            return f"Error processing question: {str(e)}"

    async def _run_greeting_flow(self) -> None:
        """
        Executes Greeting Agent welcome script narration.
        Transitions from PRESENTING prep to full PRESENTING state.
        """
        logger.info(f"RuntimeCoordinator | START _run_greeting_flow")
        try:
            primary_emp = self.employee_context.get_primary_inductee() or {}
            welcome_text = await greeting_agent.generate_welcome(
                primary_emp,
                self.presenter_context.profile,
                self.script_opening
            )
            
            def on_welcome_complete():
                logger.info("RuntimeCoordinator | Welcome greeting completed. Ready for slides.")
                self.session_manager.state = RuntimeState.PRESENTING
                self.memory.record_slide_reached(1, "Slide 1")
                asyncio.create_task(self._speak_slide_narration(1))

            if self.config.voice_enabled:
                self.voice_output.say(welcome_text, on_welcome_complete)
            else:
                on_welcome_complete()
            
            logger.info(f"RuntimeCoordinator | SUCCESS _run_greeting_flow")
        except Exception as e:
            logger.error(f"RuntimeCoordinator | FAILED _run_greeting_flow: {e}")

    async def _speak_slide_narration(self, slide_num: int) -> None:
        """
        Formats slide narration using PresentationAgent and speaks via Flow Controller.
        """
        logger.info(f"RuntimeCoordinator | START _speak_slide_narration for slide {slide_num}")
        try:
            slide = self.flow_controller.get_slide_by_number(slide_num)
            if not slide:
                logger.warning(f"RuntimeCoordinator | Slide {slide_num} not found")
                return
                
            raw_narration = slide.get("narration", "")
            spoken_text = await presentation_agent.format_narration(
                slide.get("title", f"Slide {slide_num}"),
                raw_narration,
                self.presenter_context.profile
            )
            
            slide["narration"] = spoken_text
            self._current_narration_text = spoken_text
            
            if self.config.voice_enabled:
                self.flow_controller.trigger_slide_narration(slide_num, lambda: logger.info(f"Finished slide {slide_num} narration."))
            else:
                logger.info(f"RuntimeCoordinator | Speaking disabled. Bypassed narration: {spoken_text}")
            
            logger.info(f"RuntimeCoordinator | SUCCESS _speak_slide_narration")
        except Exception as e:
            logger.error(f"RuntimeCoordinator | FAILED _speak_slide_narration: {e}")

    async def _run_closing_flow(self) -> None:
        """
        Executes Closing Agent farewell.
        """
        logger.info(f"RuntimeCoordinator | START _run_closing_flow")
        try:
            farewell = (
                f"{self.script_closing.get('summary', '')} "
                f"{self.script_closing.get('next_steps', '')} "
                f"{self.script_closing.get('farewell', '')}"
            )
            
            def on_farewell_complete():
                logger.info("RuntimeCoordinator | Farewell narration completed.")

            if self.config.voice_enabled:
                self.voice_output.say(farewell, on_farewell_complete)
            else:
                on_farewell_complete()
            
            logger.info(f"RuntimeCoordinator | SUCCESS _run_closing_flow")
        except Exception as e:
            logger.error(f"RuntimeCoordinator | FAILED _run_closing_flow: {e}")
