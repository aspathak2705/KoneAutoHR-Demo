import asyncio
import datetime
from sqlalchemy.orm import Session as DBSession
from app.models.runtime import Runtime
from app.models.session import Session
from app.services.runtime_service import runtime_service
from app.db.database import SessionLocal
from loguru import logger

class MeetingRuntimeService:
    def __init__(self):
        # Maps session_id -> running asyncio.Task
        self._active_tasks = {}

    def get_runtime(self, db: DBSession, session_id: str) -> Runtime:
        runtime = db.query(Runtime).filter(Runtime.session_id == session_id).first()
        if not runtime:
            # Create a default runtime record
            runtime = Runtime(session_id=session_id, state="READY", current_slide=0)
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

        task = asyncio.create_task(self._run_presentation_loop(session_id))
        self._active_tasks[session_id] = task
        logger.info(f"MeetingRuntime | Session: {session_id} | Presentation loop spawned.")

    def stop_meeting(self, session_id: str) -> None:
        """
        Stops the meeting presentation task.
        """
        task = self._active_tasks.pop(session_id, None)
        if task and not task.done():
            task.cancel()
            logger.info(f"MeetingRuntime | Session: {session_id} | Presentation loop cancelled.")
            
        with SessionLocal() as db:
            runtime = self.get_runtime(db, session_id)
            runtime.state = "COMPLETED"
            db.commit()

    async def advance_slide(self, session_id: str) -> int:
        with SessionLocal() as db:
            runtime = self.get_runtime(db, session_id)
            slides_ctrl = runtime_service.get_slide_controller(db, session_id)
            max_slides = slides_ctrl.get("total_slides", 0)
            if runtime.current_slide < max_slides:
                runtime.current_slide += 1
                db.commit()
                logger.info(f"MeetingRuntime | Session: {session_id} | Slide manual advance -> {runtime.current_slide}")
            return runtime.current_slide

    async def previous_slide(self, session_id: str) -> int:
        with SessionLocal() as db:
            runtime = self.get_runtime(db, session_id)
            if runtime.current_slide > 1:
                runtime.current_slide -= 1
                db.commit()
                logger.info(f"MeetingRuntime | Session: {session_id} | Slide manual backward -> {runtime.current_slide}")
            return runtime.current_slide

    async def _run_presentation_loop(self, session_id: str) -> None:
        """
        Concurrently executes the presentation states: Connecting -> Joined -> Presenting -> Q&A -> Completed.
        """
        try:
            # 1. State: JOINING (simulate browser launch & connection)
            logger.info(f"MeetingRuntime | Loop: {session_id} | Connecting to Teams...")
            self._update_runtime_state(session_id, "JOINING", slide=0)
            await asyncio.sleep(4)

            # 2. State: PRESENTING (Greeting & Introductions)
            logger.info(f"MeetingRuntime | Loop: {session_id} | Joined call. AI Self-Intro starting...")
            self._update_runtime_state(session_id, "PRESENTING", slide=1)
            
            # Fetch slide narrations to dynamically calculate ticks
            with SessionLocal() as db:
                slides_ctrl = runtime_service.get_slide_controller(db, session_id)
                total_slides = slides_ctrl.get("total_slides", 0)

            # Iterate through slide narrations
            for slide_idx in range(1, total_slides + 1):
                self._update_runtime_state(session_id, "PRESENTING", slide=slide_idx)
                logger.info(f"MeetingRuntime | Loop: {session_id} | AI narrating Slide {slide_idx}...")
                # Simulate narration delivery duration (e.g. 5 seconds per slide for demo responsiveness)
                await asyncio.sleep(6)

            # 3. State: QUESTIONS (Q&A Interactive session)
            logger.info(f"MeetingRuntime | Loop: {session_id} | Finished presentation. Ready for questions.")
            self._update_runtime_state(session_id, "QUESTIONS", slide=total_slides)
            # Wait in Q&A state for user intervention or mock completion after delay
            await asyncio.sleep(12)

            # 4. State: COMPLETED
            logger.info(f"MeetingRuntime | Loop: {session_id} | Onboarding session finalized.")
            self._update_runtime_state(session_id, "COMPLETED", slide=total_slides)

        except asyncio.CancelledError:
            logger.info(f"MeetingRuntime | Loop: {session_id} | Task was cancelled.")
        except Exception as e:
            logger.error(f"MeetingRuntime | Loop: {session_id} | Error: {e}")

    def _update_runtime_state(self, session_id: str, state: str, slide: int) -> None:
        with SessionLocal() as db:
            runtime = self.get_runtime(db, session_id)
            runtime.state = state
            runtime.current_slide = slide
            runtime.last_heartbeat = datetime.datetime.now()
            db.commit()

meeting_runtime_service = MeetingRuntimeService()
