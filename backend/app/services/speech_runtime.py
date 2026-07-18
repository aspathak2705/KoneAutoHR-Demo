import asyncio
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

    def speak(self, session_id: str, narration_text: str) -> None:
        """
        POST /runtime/{id}/speak - Queues narration and starts TTS stream.
        """
        self.stop_speaking(session_id)
        
        task = asyncio.create_task(self._run_speech_simulation(session_id, narration_text))
        self._active_tasks[session_id] = task

    def stop_speaking(self, session_id: str) -> None:
        """
        POST /runtime/{id}/stop-speaking - Interrupts/Cancels active TTS narration stream.
        """
        task = self._active_tasks.pop(session_id, None)
        if task and not task.done():
            task.cancel()
            self._update_speech_state(session_id, "INTERRUPTED")
            logger.warning(f"SpeechRuntime | Session: {session_id} | Narration stream interrupted.")
            runtime_event_bus.publish(session_id, "SpeechInterrupted", {"session_id": session_id})

    async def _run_speech_simulation(self, session_id: str, text: str) -> None:
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
            logger.info(f"SpeechRuntime | Session: {session_id} | Narration speaking completed.")
            runtime_event_bus.publish(session_id, "SpeechCompleted", {"session_id": session_id})

            # Notify Slide Controller: Auto advance current slide
            new_slide = await meeting_runtime_service.advance_slide(session_id)
            runtime_event_bus.publish(session_id, "SlideChanged", {"session_id": session_id, "current_slide": new_slide})

        except asyncio.CancelledError:
            logger.info(f"SpeechRuntime | Session: {session_id} | Narration cancelled.")
            runtime_event_bus.publish(session_id, "SpeechCancelled", {"session_id": session_id})
        except Exception as e:
            logger.error(f"SpeechRuntime | Session: {session_id} | Speech error: {e}")

    def _update_speech_state(self, session_id: str, state: str) -> None:
        with SessionLocal() as db:
            runtime = db.query(Runtime).filter(Runtime.session_id == session_id).first()
            if runtime:
                runtime.speech_state = state
                db.commit()

speech_runtime_service = SpeechRuntimeService()
