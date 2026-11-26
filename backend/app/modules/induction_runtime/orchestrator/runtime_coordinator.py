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
from app.modules.meeting_bot.bot.bot_state import BotState

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
        self.narration_state = "idle"
        self.presentation_detected: bool = False
        self.induction_started: bool = False
        self.is_hr_mode: bool = False
        
        # One-time narration tracking to prevent loops and duplicate triggers
        self._greeting_dispatched: bool = False
        self._narrated_slides: set = set()
        self._closing_dispatched: bool = False
        self._finishing_lock = asyncio.Lock()
        self._hr_flow_lock = asyncio.Lock()
        self._hr_flow_started: bool = False
        self._hr_presentation_task: Optional[asyncio.Task] = None
        self._greeting_task: Optional[asyncio.Task] = None
        self._closing_task: Optional[asyncio.Task] = None
        self._slide_narration_task: Optional[asyncio.Task] = None
        self._observer_task: Optional[asyncio.Task] = None
        
        # Lifecycle tracking
        self._browser_manager = None
        self._teams_controller = None
        self.ppt_controller = None
        
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
        - Presentation script loaded (AI Mode) or presentation manifest/audio loaded (HR Mode)
        - Employee list available
        - Presenter/trainer context configured
        
        Raises exception if any prerequisite missing.
        """
        logger.info(f"RuntimeCoordinator | START _validate_startup_prerequisites (Mode: {'HR' if self.is_hr_mode else 'AI'})")
        
        try:
            # HR Mode validates uploaded presentation package & narration, not AI script
            if self.is_hr_mode:
                from app.services.storage_service import storage_service
                session_dir = storage_service.get_session_dir(self.session_id)
                manifest_path = session_dir / "manifest.json"
                if not manifest_path.exists():
                    raise Exception(f"HR presentation manifest not found at {manifest_path}")
            else:
                # Check presentation script for AI Mode
                if not self.script_slides:
                    raise Exception("Presentation script not loaded")
            
            # Check employees
            if not self.employee_context.employees_list:
                raise Exception("Employee list not available")
            
            # Check presenter context
            if not self.presenter_context.profile:
                raise Exception("Trainer context not configured")
            
            # FAQ records are optional (may be empty if user skipped question generation)
            
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

    async def join_meeting(self, meeting_url: str, display_name: str = "KONE AI HR Officer") -> bool:
        """
        Lifecycle Phase: BROWSER_READY → JOINING → WAITING → CONNECTED
        
        Joins Teams meeting by delegating to MeetingBotService.
        """
        logger.info(f"RuntimeCoordinator | START join_meeting as {display_name}")
        
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
                    bot.context.page._session_id = self.session_id
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
            result = await meeting_bot_service.join_meeting(meeting_url, display_name, self.session_id)
            
            # Transition to WAITING
            if not await self.session_manager.transition_to(RuntimeState.WAITING):
                raise Exception("Failed to transition to WAITING state")
            
            # Transition to CONNECTED when ready
            if not await self.session_manager.transition_to(RuntimeState.CONNECTED):
                raise Exception("Failed to transition to CONNECTED state")
            
            logger.info(f"RuntimeCoordinator | SUCCESS join_meeting - Connected to meeting")
            
            # Spawn coordinator-owned observation and poll loop
            async def background_observer():
                from app.modules.presentation_observer.services.presentation_observer_service import presentation_observer_service
                logger.info(f"RuntimeCoordinator | Starting coordinator-owned observation loop for session: {self.session_id}")
                try:
                    while self.session_manager.state in [RuntimeState.CONNECTED, RuntimeState.PRESENTING]:
                        try:
                            obs = await presentation_observer_service.run_observation_cycle(self.session_id)
                            await self.poll_cycle(obs)
                        except Exception as cycle_err:
                            logger.error(f"RuntimeCoordinator | Observer loop error: {cycle_err}")
                        await asyncio.sleep(2.5)
                except asyncio.CancelledError:
                    logger.info("RuntimeCoordinator | Observer loop cancelled.")
                except Exception as loop_err:
                    logger.error(f"RuntimeCoordinator | Fatal observer loop failure: {loop_err}")

            self._observer_task = asyncio.create_task(background_observer())
            
            return True
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            clean_err = str(e)
            logger.error(f"RuntimeCoordinator | FAILED join_meeting: {clean_err}\nTraceback:\n{tb}")
            self.session_manager.failure_reason = clean_err
            await self.session_manager.transition_to(RuntimeState.FAILED, clean_err)
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
            
            # Mode detection: HR vs AI mode
            self.is_hr_mode = (ctx.get("creation_mode") == "HR")
            logger.info(f"RuntimeCoordinator | Session {self.session_id} execution mode: {'HR' if self.is_hr_mode else 'AI'}")
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
        1. Stop Teams screen sharing
        2. Leave Teams meeting via MeetingBot
        3. Close browser session
        4. Terminate PowerPoint process
        5. Cleanup Audio controller
        6. Invalidate observer
        """
        logger.info(f"RuntimeCoordinator | START _cleanup_resources")
        
        try:
            # 0. Cancel and safely await any running background tasks owned by this session
            tasks_to_cancel = [
                self._observer_task,
                self._hr_presentation_task,
                self._greeting_task,
                self._closing_task,
                self._slide_narration_task,
            ]
            active_tasks = [t for t in tasks_to_cancel if t and not t.done()]
            for t in active_tasks:
                t.cancel()
            if active_tasks:
                await asyncio.gather(*active_tasks, return_exceptions=True)
            
            # Stop voice output / audio tasks for this session
            if hasattr(self, "voice_output") and self.voice_output:
                try:
                    self.voice_output.stop()
                except Exception as vo_err:
                    logger.debug(f"RuntimeCoordinator | VoiceOutput stop notice: {vo_err}")

            # Clean up temporary audio slices older than 1 hour for this session
            try:
                from app.services.storage_service import storage_service
                storage_service.cleanup_expired_generated_audio(self.session_id, max_age_seconds=3600.0)
            except Exception as clean_err:
                logger.debug(f"RuntimeCoordinator | Temporary audio cleanup notice: {clean_err}")

            # 1. Stop Teams screen sharing if active
            from app.modules.meeting_bot.services.meeting_bot_service import meeting_bot_service
            bot = meeting_bot_service.get_bot(self.session_id)
            if bot and bot.context.page and not bot.context.page.is_closed():
                try:
                    from app.modules.meeting_bot.teams.teams_controller import teams_controller
                    logger.info("RuntimeCoordinator | Stopping Teams screen share...")
                    await teams_controller.stop_sharing(bot.context.page)
                except Exception as share_stop_err:
                    logger.warning(f"RuntimeCoordinator | Stop sharing notice: {share_stop_err}")

            # 2. Leave Teams meeting and disconnect call
            if bot and getattr(bot.context, "state", None) == BotState.CONNECTED:
                try:
                    logger.info("RuntimeCoordinator | Leaving Teams meeting dynamically...")
                    await bot.leave()
                except Exception as leave_err:
                    logger.warning(f"RuntimeCoordinator | Bot leave notice: {leave_err}")

            # Cleanup Teams controller reference
            if self._teams_controller:
                self._teams_controller = None
            
            # 3. Cleanup browser for this session
            if self._browser_manager:
                try:
                    logger.info(f"RuntimeCoordinator | Cleaning up browser for session {self.session_id}")
                    await self._browser_manager.close(self.session_id)
                    self._browser_manager = None
                except Exception as e:
                    logger.error(f"RuntimeCoordinator | Failed to cleanup browser: {e}")

            # 4. Safely close PowerPoint slideshow instance
            if self.ppt_controller:
                try:
                    await self.ppt_controller.close_presentation()
                    logger.info("RuntimeCoordinator | PowerPoint presentation closed safely via COM.")
                except Exception as ppt_err:
                    logger.warning(f"RuntimeCoordinator | PowerPoint cleanup notice: {ppt_err}")
                self.ppt_controller = None

            # 5. Terminate persistent PowerShell audio preloader process
            try:
                from app.modules.meeting_bot.media.audio_controller import cleanup_audio_controller
                cleanup_audio_controller(self.session_id)
                logger.info("RuntimeCoordinator | Preloader PowerShell engine terminated.")
            except Exception as e:
                logger.warning(f"RuntimeCoordinator | Audio preloader cleanup failed: {e}")

            # 6. Invalidate live presentation detection flag and observer context
            self.presentation_detected = False
            try:
                from app.modules.presentation_observer.services.presentation_observer_service import presentation_observer_service
                presentation_observer_service.remove_observer(self.session_id)
            except Exception as e:
                logger.warning(f"RuntimeCoordinator | Observer cleanup notice: {e}")

            # 7. Disassociate coordinator from RuntimeService cache upon execution completion
            try:
                from app.services.runtime_service import runtime_service
                runtime_service.remove_coordinator(self.session_id)
            except Exception as e:
                logger.debug(f"RuntimeCoordinator | Coordinator cache removal notice: {e}")

            logger.info(f"RuntimeCoordinator | SUCCESS _cleanup_resources")
        except Exception as e:
            logger.error(f"RuntimeCoordinator | FAILED _cleanup_resources: {e}")

    async def poll_cycle(self, observation: Observation) -> None:
        """
        Main execution loop step. Driven by updates from the Presentation Observer.
        Uses new locked state machine.
        """
        # If already in terminal or finishing state, ignore observation cycles completely
        if self.session_manager.state in [RuntimeState.FINISHED, RuntimeState.STOPPING, RuntimeState.STOPPED, RuntimeState.FAILED]:
            return

        logger.debug(f"RuntimeCoordinator | Polling cycle | Observation State: {observation.observation_state} | Active State: {self.session_manager.state.value}")

        # Update presentation detection status
        from app.modules.semantic_browser.models.presentation_state import PresentationMode
        presentation_active = (
            str(observation.presentation_state) in ["POWERPOINT_SHARED", "SCREEN_SHARING", "PresentationMode.POWERPOINT_SHARED", "PresentationMode.SCREEN_SHARING"] or
            getattr(observation, "presentation_state", None) in [PresentationMode.POWERPOINT_SHARED, PresentationMode.SCREEN_SHARING]
        )
        self.presentation_detected = presentation_active

        # Transition: CONNECTED → PRESENTING only when induction has been started/authorized by HR
        # Enforce strict one-time greeting dispatch for AI mode, or HR presentation flow for HR mode
        if self.induction_started and self.session_manager.state == RuntimeState.CONNECTED and presentation_active:
            if self.is_hr_mode:
                if not self._hr_flow_started:
                    self._hr_flow_started = True
                    logger.info("RuntimeCoordinator | HR Mode presentation active. Launching HR presentation flow.")
                    if await self.session_manager.transition_to(RuntimeState.PRESENTING):
                        self._hr_presentation_task = asyncio.create_task(self._run_hr_presentation_flow())
                        return
                    else:
                        logger.warning("RuntimeCoordinator | Transition to PRESENTING failed for HR Mode presentation.")
            else:
                if not self._greeting_dispatched:
                    logger.info("RuntimeCoordinator | AI Mode presentation active. Launching greeting flow.")
                    if await self.session_manager.transition_to(RuntimeState.PRESENTING):
                        self._greeting_dispatched = True
                        self._greeting_task = asyncio.create_task(self._run_greeting_flow())
                        return

        # Handle slide changes during PRESENTING (AI Mode only)
        if not self.is_hr_mode and (ObservationEvent.SLIDE_CHANGED in observation.events or (self.session_manager.state == RuntimeState.PRESENTING and observation.current_slide > 0 and observation.current_slide != self.memory.current_slide_number)):
            if self.session_manager.state == RuntimeState.PRESENTING:
                slide_num = observation.current_slide if observation.current_slide > 0 else observation.timeline_index
                if slide_num > 0 and slide_num not in self._narrated_slides:
                    logger.info(f"RuntimeCoordinator | Slide changed to {slide_num}")
                    self.memory.record_slide_reached(slide_num, f"Slide {slide_num}")
                    
                    if self.config.voice_enabled:
                        self.voice_output.interrupt()
                    
                    self._slide_narration_task = asyncio.create_task(self._speak_slide_narration(slide_num))

        # Transition: PRESENTING → CONNECTED (presentation paused/ended)
        if ObservationEvent.PRESENTATION_ENDED in observation.events:
            if self.session_manager.state == RuntimeState.PRESENTING:
                logger.info("RuntimeCoordinator | Presentation share ended or paused. Pausing narration and remaining in meeting.")
                if self.config.voice_enabled:
                    self.voice_output.interrupt()
                if not self.is_hr_mode:
                    total_slides = max(len(self.flow_controller.slides_script), len(self.script_slides), 1)
                    if len(self._narrated_slides) >= total_slides:
                        self._closing_task = asyncio.create_task(self._run_closing_flow())
                    else:
                        await self.session_manager.transition_to(RuntimeState.CONNECTED)
                else:
                    await self.session_manager.transition_to(RuntimeState.CONNECTED)

    async def inject_question(self, speaker: str, question_text: str) -> str:
        """
        Simulates chat question injection. Interrupts current narration and answers.
        Only allowed during PRESENTING state in AI Mode.
        In HR Mode, question injection is explicitly unsupported to prevent narration collision.
        """
        logger.info(f"RuntimeCoordinator | START inject_question from {speaker}")
        
        try:
            if self.is_hr_mode:
                msg = "Question injection is not supported during HR Mode presentation playback."
                logger.warning(f"RuntimeCoordinator | {msg}")
                raise ValueError(msg)

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
        Ensures strict one-time execution per session.
        """
        if self._greeting_dispatched and getattr(self, "_greeting_running", False):
            logger.info("RuntimeCoordinator | Greeting flow already executing or dispatched. Skipping duplicate.")
            return

        self._greeting_running = True
        self._greeting_dispatched = True
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
                self.narration_state = "finished_greeting"
                self.memory.record_slide_reached(1, "Slide 1")
                self._slide_narration_task = asyncio.create_task(self._speak_slide_narration(1))

            self.narration_state = "speaking_greeting"
            if self.config.voice_enabled:
                self.voice_output.say(welcome_text, on_welcome_complete, audio_file="greeting.mp3")
            else:
                on_welcome_complete()
            
            logger.info(f"RuntimeCoordinator | SUCCESS _run_greeting_flow")
        except Exception as e:
            logger.error(f"RuntimeCoordinator | FAILED _run_greeting_flow: {e}")
        finally:
            self._greeting_running = False

    async def _speak_slide_narration(self, slide_num: int) -> None:
        """
        Formats slide narration using PresentationAgent and speaks via Flow Controller.
        Idempotent: Each slide narrated at most once.
        Automatically triggers closing and finish when all slides have finished narration.
        """
        if slide_num in self._narrated_slides:
            logger.info(f"RuntimeCoordinator | Slide {slide_num} already narrated or running. Skipping duplicate.")
            return

        self._narrated_slides.add(slide_num)
        logger.info(f"RuntimeCoordinator | START _speak_slide_narration for slide {slide_num}")
        try:
            slide = self.flow_controller.get_slide_by_number(slide_num)
            if not slide:
                logger.warning(f"RuntimeCoordinator | Slide {slide_num} not found")
                # If slide not found, check if deck is finished
                total_slides = max(len(self.flow_controller.slides_script), len(self.script_slides), 1)
                if len(self._narrated_slides) >= total_slides:
                    asyncio.create_task(self._run_closing_flow())
                return
                
            raw_narration = slide.get("narration", "")
            spoken_text = await presentation_agent.format_narration(
                slide.get("title", f"Slide {slide_num}"),
                raw_narration,
                self.presenter_context.profile
            )
            
            slide["narration"] = spoken_text
            self._current_narration_text = spoken_text
            
            async def on_complete_async():
                logger.info(f"Finished slide {slide_num} narration.")
                self.narration_state = f"finished_slide_{slide_num}"
                
                # Check if all slides in presentation script have finished narration
                total_slides = max(len(self.flow_controller.slides_script), len(self.script_slides), 1)
                if len(self._narrated_slides) >= total_slides:
                    logger.info(f"RuntimeCoordinator | Final slide ({slide_num}/{total_slides}) completed narration. Proceeding to closing flow.")
                    self._closing_task = asyncio.create_task(self._run_closing_flow())
                    return

                # AI Mode autonomous progression: advance PowerPoint to slide_num + 1
                next_slide = slide_num + 1
                if next_slide <= total_slides:
                    logger.info(f"RuntimeCoordinator | AI Mode advancing PowerPoint slideshow to slide {next_slide}")
                    try:
                        from app.modules.presentation.powerpoint_controller import PowerPointController
                        if not self.ppt_controller or not self.ppt_controller.slide_show:
                            self.ppt_controller = PowerPointController()
                            self.ppt_controller.attach_active()
                        
                        await self.ppt_controller.goto_slide(next_slide)
                        self.memory.record_slide_reached(next_slide, f"Slide {next_slide}")
                        self._slide_narration_task = asyncio.create_task(self._speak_slide_narration(next_slide))
                    except Exception as adv_err:
                        logger.error(f"RuntimeCoordinator | AI Mode slide advance to {next_slide} failed: {adv_err}")

            def on_complete():
                asyncio.create_task(on_complete_async())

            self.narration_state = f"speaking_slide_{slide_num}"
            if self.config.voice_enabled:
                self.flow_controller.trigger_slide_narration(slide_num, on_complete)
            else:
                logger.info(f"RuntimeCoordinator | Speaking disabled. Bypassed narration: {spoken_text}")
                on_complete()
            
            logger.info(f"RuntimeCoordinator | SUCCESS _speak_slide_narration")
        except Exception as e:
            logger.error(f"RuntimeCoordinator | FAILED _speak_slide_narration: {e}")

    async def _run_hr_presentation_flow(self) -> None:
        """
        Executes HR Mode induction presentation flow.
        Uses uploaded audio per slide in slide sequence (via presentation timeline & manifest).
        Waits for natural completion of each slide's audio before advancing.
        Upon final slide audio completion, triggers stop sharing, leaves Teams, and marks COMPLETED.
        Strictly separated from AI Mode: does NOT run AI greeting, AI narration, or AI closing.
        Guaranteed to execute exactly once per session via atomic lock & flags.
        """
        async with self._hr_flow_lock:
            if getattr(self, "_hr_flow_executing", False):
                logger.info("RuntimeCoordinator | HR presentation flow already running. Skipping duplicate call.")
                return
            self._hr_flow_executing = True
            self._hr_flow_started = True

        logger.info(f"RuntimeCoordinator | START _run_hr_presentation_flow for session {self.session_id}")
        try:
            from app.services.storage_service import storage_service
            from app.modules.meeting_bot.media.audio_controller import get_audio_controller
            from app.modules.presentation.powerpoint_controller import PowerPointController
            from app.modules.presentation.timeline_executor import TimelineExecutor
            import json

            session_dir = storage_service.get_session_dir(self.session_id)
            manifest_path = session_dir / "manifest.json"
            if not manifest_path.exists():
                raise FileNotFoundError(f"Manifest not found for HR presentation: {manifest_path}")

            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)

            timeline_file = manifest.get("timeline", "presentation_timeline.json")
            timeline_path = session_dir / timeline_file
            if not timeline_path.exists():
                raise FileNotFoundError(f"Timeline not found for HR presentation: {timeline_path}")

            audio_file = manifest.get("audio", "narration.wav")
            audio_path = session_dir / audio_file
            if not audio_path.exists():
                audio_path = session_dir / "audio" / audio_file
            if not audio_path.exists():
                audio_path = storage_service.get_generated_audio_dir(self.session_id) / audio_file

            if not audio_path.exists():
                raise FileNotFoundError(f"HR narration audio not found: {audio_path}")

            audio = get_audio_controller(self.session_id)
            if not audio.validate_audio_route():
                raise RuntimeError("Audio route validation failed before HR narration playback")

            # Use existing ppt_controller or attach to active PowerPoint slideshow instance
            if self.ppt_controller and self.ppt_controller.slide_show:
                ppt_ctrl = self.ppt_controller
            else:
                ppt_ctrl = PowerPointController()
                ppt_ctrl.attach_active()
                self.ppt_controller = ppt_ctrl

            # Load slide metadata for media timing coordination if present
            slides_metadata = []
            slides_meta_path = session_dir / "slides_metadata.json"
            if slides_meta_path.exists():
                try:
                    with open(slides_meta_path, "r", encoding="utf-8") as smf:
                        slides_metadata = json.load(smf)
                except Exception as sm_err:
                    logger.warning(f"RuntimeCoordinator | Could not read slides_metadata.json: {sm_err}")

            # Map slide number to video info (from slides_metadata.json or dynamic COM scan)
            slide_videos = {}
            for s in slides_metadata:
                s_num = s.get("slide_number")
                v_meta = s.get("video_metadata", [])
                if s_num and v_meta:
                    slide_videos[s_num] = v_meta

            # Fallback dynamic scan of media shapes from presentation COM
            if not slide_videos and ppt_ctrl.presentation:
                try:
                    pres_com = ppt_ctrl.presentation
                    for s_idx in range(1, pres_com.Slides.Count + 1):
                        shapes = ppt_ctrl.get_slide_media_shapes(s_idx)
                        if shapes:
                            v_list = []
                            for shp in shapes:
                                dur = 0.0
                                try:
                                    if hasattr(shp, "MediaFormat") and shp.MediaFormat.Length > 0:
                                        dur = shp.MediaFormat.Length / 1000.0
                                except Exception:
                                    pass
                                v_list.append({
                                    "shape_id": shp.Id,
                                    "shape_name": shp.Name,
                                    "duration": dur,
                                    "supported": True
                                })
                            slide_videos[s_idx] = v_list
                    if slide_videos:
                        logger.info(f"RuntimeCoordinator | Dynamically discovered media on slides: {list(slide_videos.keys())}")
                except Exception as dyn_err:
                    logger.debug(f"RuntimeCoordinator | Dynamic media scan notice: {dyn_err}")

            current_visible_slide = ppt_ctrl.get_current_slide_index()
            slide_start_monotonic = {}
            slide_start_monotonic[current_visible_slide] = asyncio.get_running_loop().time()

            # Map slide number to narration window (start_ms, end_ms) based on timeline / manifest
            executor = TimelineExecutor(str(timeline_path))
            slide_narration_bounds = {}
            events_list = sorted(executor.events, key=lambda x: x.get("time_ms", 0))
            for i, ev in enumerate(events_list):
                s_num = ev.get("slide")
                st_ms = float(ev.get("time_ms", 0))
                s_audio_meta = manifest.get("slide_audio_metadata", {}).get(str(s_num), {})
                dur_ms = s_audio_meta.get("duration_ms")
                if dur_ms is not None and dur_ms > 0:
                    end_ms = st_ms + float(dur_ms)
                elif i + 1 < len(events_list):
                    end_ms = float(events_list[i + 1].get("time_ms", 0))
                else:
                    end_ms = float(manifest.get("duration_ms", st_ms))
                slide_narration_bounds[s_num] = (st_ms, end_ms)

            slide_video_started = set()
            slide_video_finished = set()
            slide_video_play_count = {}

            def is_slide_media_busy(slide_num: int) -> bool:
                """
                Checks if slide_num has an embedded video that is currently playing or has not
                met its required playback duration.
                """
                if not ppt_ctrl:
                    return False
                if slide_num not in slide_videos:
                    return False
                if slide_num in slide_video_finished:
                    return False

                if slide_num in slide_video_started:
                    # 1. Check COM player state
                    if ppt_ctrl.is_media_playing_on_slide(slide_num):
                        return True

                    # 2. Check duration elapsed
                    has_known_duration = False
                    for v in slide_videos[slide_num]:
                        dur = v.get("duration")
                        if dur and dur > 0:
                            has_known_duration = True
                            start_t = slide_start_monotonic.get(f"{slide_num}_video")
                            if start_t:
                                elapsed = asyncio.get_running_loop().time() - start_t
                                if elapsed < dur:
                                    return True

                    # 3. Minimum buffer if duration unknown
                    if not has_known_duration:
                        start_t = slide_start_monotonic.get(f"{slide_num}_video")
                        if start_t:
                            elapsed = asyncio.get_running_loop().time() - start_t
                            if elapsed < 2.0:
                                return True

                    slide_video_finished.add(slide_num)
                    ppt_ctrl.stop_media_on_slide(slide_num)
                    logger.info(
                        f"RuntimeCoordinator | [MEDIA_STATE] Session: {self.session_id} | "
                        f"Slide: {slide_num} | State: COMPLETED | Total Starts: {slide_video_play_count.get(slide_num, 0)}"
                    )
                    return False

                # Video hasn't started yet: slide is busy waiting for video to play
                return True

            async def play_slide_video_now(slide_num: int, trigger_source: str = "orchestrator"):
                """
                Starts embedded video on slide_num.
                Guaranteed to trigger exactly once per slide visit.
                """
                if slide_num not in slide_videos or slide_num in slide_video_started:
                    logger.debug(
                        f"RuntimeCoordinator | Ignoring duplicate video start request on slide {slide_num} "
                        f"from {trigger_source}. Already started={slide_num in slide_video_started}"
                    )
                    return

                slide_video_started.add(slide_num)
                slide_video_play_count[slide_num] = slide_video_play_count.get(slide_num, 0) + 1
                slide_start_monotonic[f"{slide_num}_video"] = asyncio.get_running_loop().time()

                v_list = slide_videos.get(slide_num, [])
                shape_ids = [v.get("shape_id") for v in v_list]
                logger.info(
                    f"RuntimeCoordinator | [MEDIA_TRIGGER] Session: {self.session_id} | "
                    f"Slide: {slide_num} | Trigger: {trigger_source} | Shapes: {shape_ids} | "
                    f"Start Count: {slide_video_play_count[slide_num]}"
                )

                for v in v_list:
                    ppt_ctrl.play_media_on_slide(slide_num, v.get("shape_id"))

            async def handle_goto_slide(slide_num: int):
                nonlocal current_visible_slide
                logger.info(f"RuntimeCoordinator | HR Mode goto_slide {slide_num} (current: {current_visible_slide})")
                if current_visible_slide != slide_num:
                    await ppt_ctrl.goto_slide(slide_num)
                    current_visible_slide = slide_num
                    slide_start_monotonic[current_visible_slide] = asyncio.get_running_loop().time()

                self.memory.record_slide_reached(slide_num, f"Slide {slide_num}")
                self.narration_state = f"speaking_slide_{slide_num}"

                # For silent video slides without narration, play video immediately on slide entry
                if current_visible_slide in slide_videos:
                    bounds = slide_narration_bounds.get(current_visible_slide)
                    has_narration = False
                    if bounds:
                        st_ms, end_ms = bounds
                        s_meta = manifest.get("slide_audio_metadata", {}).get(str(current_visible_slide), {})
                        if s_meta.get("type") != "SILENT" and (end_ms - st_ms) > 100:
                            has_narration = True

                    if not has_narration:
                        await play_slide_video_now(current_visible_slide, trigger_source="slide_entry_silent")

            # Start concatenated HR narration playback
            logger.info(f"RuntimeCoordinator | Playing HR narration audio: {audio_path}")
            audio.play_narration(audio_path, manifest.get("duration_ms"))

            # Execute timeline synchronized with audio position and video holds
            await executor.execute(
                audio_controller=audio,
                on_goto_slide=handle_goto_slide,
                is_slide_busy=is_slide_media_busy,
                get_current_slide=lambda: ppt_ctrl.get_current_slide_index(),
                start_slide_media=play_slide_video_now,
            )

            # Wait for final slide narration audio playback to finish naturally
            logger.info("RuntimeCoordinator | HR Timeline finished. Waiting for final slide audio to finish naturally...")
            while audio.playing:
                await asyncio.sleep(0.3)

            logger.info("RuntimeCoordinator | HR Presentation audio playback completed naturally for all slides.")
            self.narration_state = "finished_closing"

            # Stop sharing, leave Teams, close resources, mark session COMPLETED
            await self._finalize_and_leave()
            logger.info(f"RuntimeCoordinator | SUCCESS _run_hr_presentation_flow for session {self.session_id}")

        except Exception as e:
            logger.error(f"RuntimeCoordinator | FAILED _run_hr_presentation_flow: {e}")
            await self._finalize_and_leave()

    async def _run_closing_flow(self) -> None:
        """
        Executes Closing Agent farewell.
        Upon farewell audio completion, triggers graceful finish, Teams stop-share, and leave.
        Idempotent: Triggers closing flow and termination exactly once.
        """
        if self._closing_dispatched:
            logger.info("RuntimeCoordinator | Closing flow already dispatched. Skipping duplicate.")
            return

        self._closing_dispatched = True
        logger.info(f"RuntimeCoordinator | START _run_closing_flow")
        try:
            farewell = (
                f"{self.script_closing.get('summary', '')} "
                f"{self.script_closing.get('next_steps', '')} "
                f"{self.script_closing.get('farewell', '')}"
            ).strip() or "Thank you for attending the KONE onboarding session. Welcome to the team!"
            
            def on_farewell_complete():
                logger.info("RuntimeCoordinator | Farewell narration completed. Triggering automatic session finalization and departure.")
                self.narration_state = "finished_closing"
                asyncio.create_task(self._finalize_and_leave())

            self.narration_state = "speaking_closing"
            if self.config.voice_enabled:
                self.voice_output.say(farewell, on_farewell_complete, audio_file="closing.mp3")
            else:
                on_farewell_complete()
            
            logger.info(f"RuntimeCoordinator | SUCCESS _run_closing_flow")
        except Exception as e:
            logger.error(f"RuntimeCoordinator | FAILED _run_closing_flow: {e}")
            # If closing flow fails to speak, still finalize session cleanly
            asyncio.create_task(self._finalize_and_leave())

    async def _finalize_and_leave(self) -> None:
        """
        Concurrency-protected automatic termination and Teams meeting departure.
        Transitions state: PRESENTING → FINISHED → STOPPING → STOPPED
        Releases presentation, browser, audio, and leaves Teams call.
        """
        async with self._finishing_lock:
            if self.session_manager.state in [RuntimeState.FINISHED, RuntimeState.STOPPING, RuntimeState.STOPPED]:
                logger.info("RuntimeCoordinator | Finalize and leave already completed or in progress.")
                return
            logger.info(f"RuntimeCoordinator | Automatic meeting departure triggered for session: {self.session_id}")
            await self.finish_presentation()
