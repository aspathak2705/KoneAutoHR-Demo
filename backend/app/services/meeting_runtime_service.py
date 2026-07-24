import asyncio
import datetime
from typing import Optional
from sqlalchemy.orm import Session as DBSession
from app.models.runtime import Runtime
from app.models.session import Session
from app.models.meeting import Meeting
from app.services.runtime_service import runtime_service
from app.db.database import SessionLocal
from app.core.task_registry import async_task_registry
from app.core.cleanup_manager import cleanup_manager
from app.modules.meeting_bot.services.meeting_bot_service import meeting_bot_service
from app.modules.presentation_observer.services.presentation_observer_service import presentation_observer_service
from loguru import logger

class MeetingRuntimeService:
    def __init__(self):
        # Maps session_id -> running asyncio.Task
        self._active_tasks = {}

    def get_runtime(self, db: DBSession, session_id: str) -> Optional[Runtime]:
        sess = db.query(Session).filter(Session.id == session_id).first()
        if not sess:
            return None
        runtime = db.query(Runtime).filter(Runtime.session_id == session_id).first()
        if not runtime:
            runtime = Runtime(session_id=session_id, state="PREPARING", current_slide=0)
            db.add(runtime)
            db.commit()
            db.refresh(runtime)
        return runtime

    def start_meeting(self, session_id: str) -> None:
        """
        Launches the background runtime presentation engine task.
        """
        if session_id in self._active_tasks and not self._active_tasks[session_id].done():
            logger.warning(f"MeetingRuntime | Session: {session_id} | Meeting already running.")
            return

        task = asyncio.create_task(self._run_observer_loop(session_id))
        self._active_tasks[session_id] = task
        async_task_registry.register(session_id, task)
        logger.info(f"MeetingRuntime | Session: {session_id} | Presentation observer loop spawned.")

    def stop_meeting(self, session_id: str) -> None:
        """
        Stops the meeting presentation task and triggers centralized cleanup.
        """
        task = self._active_tasks.pop(session_id, None)
        if task and not task.done():
            task.cancel()
            logger.info(f"MeetingRuntime | Session: {session_id} | Presentation loop cancelled.")
            
        async def shutdown():
            await cleanup_manager.cleanup_session(session_id)
            with SessionLocal() as db:
                runtime = self.get_runtime(db, session_id)
                if runtime:
                    runtime.state = "COMPLETED"
                    db.commit()
        
        asyncio.create_task(shutdown())

    async def advance_slide(self, session_id: str) -> int:
        with SessionLocal() as db:
            runtime = self.get_runtime(db, session_id)
            slides_ctrl = runtime_service.get_slide_controller(db, session_id)
            max_slides = slides_ctrl.get("total_slides", 0)
            if runtime.current_slide < max_slides:
                runtime.current_slide += 1
                db.commit()
                logger.info(f"MeetingRuntime | Session: {session_id} | Slide manual advance -> {runtime.current_slide}")
                
                # Update coordinator state manually on manual advance
                coordinator = runtime_service.get_coordinator(db, session_id)
                coordinator.memory.record_slide_reached(runtime.current_slide, f"Slide {runtime.current_slide}")
                if coordinator.config.voice_enabled:
                    coordinator.voice_output.interrupt()
                    # Trigger narration
                    asyncio.create_task(coordinator._speak_slide_narration(runtime.current_slide))
            return runtime.current_slide

    async def previous_slide(self, session_id: str) -> int:
        with SessionLocal() as db:
            runtime = self.get_runtime(db, session_id)
            if runtime.current_slide > 1:
                runtime.current_slide -= 1
                db.commit()
                logger.info(f"MeetingRuntime | Session: {session_id} | Slide manual backward -> {runtime.current_slide}")
                
                # Update coordinator state manually
                coordinator = runtime_service.get_coordinator(db, session_id)
                coordinator.memory.record_slide_reached(runtime.current_slide, f"Slide {runtime.current_slide}")
                if coordinator.config.voice_enabled:
                    coordinator.voice_output.interrupt()
                    # Trigger narration
                    asyncio.create_task(coordinator._speak_slide_narration(runtime.current_slide))
            return runtime.current_slide

    async def _run_observer_loop(self, session_id: str) -> None:
        """
        Concurrently executes the presentation states by driving the Playwright MeetingBot
        and checking observation cycles.
        """
        try:
            # 1. Initialize DB state and fetch meeting URL
            meeting_url = ""
            with SessionLocal() as db:
                runtime = self.get_runtime(db, session_id)
                if runtime.state == "PREPARING" or runtime.state == "IDLE":
                    runtime.state = "CREATED"
                    db.commit()
                
                meeting = db.query(Meeting).filter(Meeting.session_id == session_id).first()
                if meeting:
                    meeting_url = meeting.teams_meeting_url

            if not meeting_url:
                raise ValueError(f"No Teams meeting URL configured for Session: {session_id}")

            # 2. Launch MeetingBot browser context and join meeting
            logger.info(f"MeetingRuntime | Session: {session_id} | Launching MeetingBot browser...")
            await meeting_bot_service.start_bot(session_id)
            
            logger.info(f"MeetingRuntime | Session: {session_id} | Joining Teams meeting...")
            await meeting_bot_service.join_meeting(meeting_url, "KONE AI Bot", session_id)

            # 3. Enter real observer-driven loop
            logger.info(f"MeetingRuntime | Session: {session_id} | Starting observation scan loop.")
            while True:
                obs = await presentation_observer_service.run_observation_cycle(session_id)
                
                with SessionLocal() as db:
                    coordinator = runtime_service.get_coordinator(db, session_id)
                    await coordinator.poll_cycle(obs)
                    
                    current_state = coordinator.session_manager.state.value
                    
                    # Update database runtime state
                    db_runtime = self.get_runtime(db, session_id)
                    db_runtime.state = current_state
                    db_runtime.current_slide = coordinator.memory.current_slide_number
                    db_runtime.last_heartbeat = datetime.datetime.now()
                    db.commit()
                    
                    if current_state == "COMPLETED":
                        logger.info(f"MeetingRuntime | Session: {session_id} | Coordinator reports COMPLETED. Exiting loop.")
                        break

                await asyncio.sleep(2.5)

        except asyncio.CancelledError:
            logger.info(f"MeetingRuntime | Session: {session_id} | Observer loop cancelled.")
        except Exception as e:
            logger.exception(f"MeetingRuntime | Session: {session_id} | Fatal error in observer loop: {e}")
            await self._handle_fatal_failure(session_id, str(e))

    async def _handle_fatal_failure(self, session_id: str, error_msg: str) -> None:
        logger.error(f"MeetingRuntime | Fatal failure detected for session: {session_id}. Error: {error_msg}")
        try:
            with SessionLocal() as db:
                runtime = self.get_runtime(db, session_id)
                if runtime:
                    runtime.state = "FAILED"
                    runtime.last_error = error_msg
                    db.commit()
        except Exception as e:
            logger.error(f"MeetingRuntime | Failed to update runtime state to FAILED: {e}")
            
        await cleanup_manager.cleanup_session(session_id)

meeting_runtime_service = MeetingRuntimeService()
