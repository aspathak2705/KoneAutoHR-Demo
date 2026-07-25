import asyncio
from typing import Callable, Any
from sqlalchemy.orm import Session as DBSession
from app.db.database import SessionLocal
from app.models.runtime import Runtime
from app.services.event_bus import runtime_event_bus
from app.services.meeting_runtime_service import meeting_runtime_service
from loguru import logger

class SpeechRuntimeService:
    def __init__(self):
        # Maps session_id -> active speaking task
        self._active_tasks = {}
        # Maps session_id -> remaining speech info for pause/resume
        self._paused_states = {}

    def speak(self, session_id: str, narration_text: str, completion_callback: Callable[[str], None] = None) -> None:
        """
        POST /runtime/{id}/speak - Queues narration and starts TTS stream.
        """
        self.cancel(session_id)
        
        task = asyncio.create_task(
            self._run_speech_simulation(session_id, narration_text, completion_callback)
        )
        self._active_tasks[session_id] = task

    def pause(self, session_id: str) -> None:
        """
        Pauses active TTS narration speaking stream, tracking remaining characters left.
        """
        task_info = self._active_tasks.pop(session_id, None)
        if task_info and not task_info.done():
            task_info.cancel()
            self._update_speech_state(session_id, "IDLE")
            # Calculate remaining speech delay (mocked duration)
            self._paused_states[session_id] = {
                "text": "Remaining text stream content...",
                "callback": None
            }
            logger.info(f"SpeechRuntime | Session: {session_id} | Narration speaking paused.")
            runtime_event_bus.publish(session_id, "SpeechInterrupted", {"session_id": session_id})

    def resume(self, session_id: str) -> None:
        """
        Resumes paused narration speech streams.
        """
        paused = self._paused_states.pop(session_id, None)
        if paused:
            logger.info(f"SpeechRuntime | Session: {session_id} | Resuming speech stream...")
            self.speak(session_id, paused["text"], paused["callback"])

    def cancel(self, session_id: str) -> None:
        """
        Cancels active speech, resetting all narration queues.
        """
        task = self._active_tasks.pop(session_id, None)
        if task and not task.done():
            task.cancel()
            runtime_event_bus.publish(session_id, "SpeechCancelled", {"session_id": session_id})
        self._paused_states.pop(session_id, None)
        self._update_speech_state(session_id, "IDLE")

    def stop_speaking(self, session_id: str) -> None:
        self.cancel(session_id)

    def retry(self, session_id: str, narration_text: str) -> None:
        """
        Retries narration speech playback from start.
        """
        logger.info(f"SpeechRuntime | Session: {session_id} | Retrying narration speech...")
        self.speak(session_id, narration_text)

    async def _run_speech_simulation(self, session_id: str, text: str, callback: Callable[[str], None] = None) -> None:
        try:
            self._update_speech_state(session_id, "SPEAKING")
            logger.info(f"SpeechRuntime | Session: {session_id} | Speaking: '{text[:60]}...'")
            runtime_event_bus.publish(session_id, "SpeechStarted", {"session_id": session_id, "text": text})

            # Calculate voice timeline duration (15 characters per second rate)
            char_count = len(text)
            duration = max(3.0, char_count / 15.0)
            await asyncio.sleep(duration)

            # Speech completed successfully
            self._update_speech_state(session_id, "IDLE")
            logger.info(f"SpeechRuntime | Session: {session_id} | Narration speaking completed successfully.")
            runtime_event_bus.publish(session_id, "SpeechCompleted", {"session_id": session_id})

            # Fire completion callback to advance slide
            if callback:
                callback(session_id)
            else:
                # Default completion callback: Auto advance slide controller
                new_slide = await meeting_runtime_service.advance_slide(session_id)
                runtime_event_bus.publish(session_id, "SlideChanged", {"session_id": session_id, "current_slide": new_slide})

        except asyncio.CancelledError:
            logger.info(f"SpeechRuntime | Session: {session_id} | Speaking task cancelled.")
        except Exception as e:
            logger.error(f"SpeechRuntime | Session: {session_id} | Speech error: {e}")

    def _update_speech_state(self, session_id: str, state: str) -> None:
        with SessionLocal() as db:
            runtime = db.query(Runtime).filter(Runtime.session_id == session_id).first()
            if runtime:
                runtime.speech_state = state
                db.commit()

speech_runtime_service = SpeechRuntimeService()
