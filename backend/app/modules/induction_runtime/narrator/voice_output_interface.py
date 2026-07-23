import asyncio
from typing import Callable, Optional
from loguru import logger

class VoiceOutputInterface:
    def say(self, text: str, callback: Optional[Callable[[], None]] = None) -> None:
        """
        Initiates spoken voice stream out of the text parameter.
        Triggers the callback when playback has finished.
        """
        raise NotImplementedError

    def interrupt(self) -> None:
        """
        Interrupts current active voice playback stream.
        """
        raise NotImplementedError

    def stop(self) -> None:
        """
        Stops all voice output streams.
        """
        raise NotImplementedError

    def resume(self) -> None:
        """
        Resumes playing back the last paused voice stream.
        """
        raise NotImplementedError


class DefaultVoiceOutput(VoiceOutputInterface):
    def __init__(self):
        self._active_task: Optional[asyncio.Task] = None
        self._paused_text: Optional[str] = None
        self._paused_callback: Optional[Callable[[], None]] = None
        self.is_speaking: bool = False

    def say(self, text: str, callback: Optional[Callable[[], None]] = None) -> None:
        """
        Simulates speaking by printing text, computing simulated duration, and executing callback.
        """
        self.stop()
        self.is_speaking = True
        self._active_task = asyncio.create_task(
            self._run_speaking_simulation(text, callback)
        )

    def interrupt(self) -> None:
        """
        Interrupts speech playback and stores state for potential resuming.
        """
        if self._active_task and not self._active_task.done():
            self._active_task.cancel()
            self._paused_text = "Remaining text stream content..."
            logger.info("VoiceOutput | Voice playback interrupted.")
        self.is_speaking = False

    def stop(self) -> None:
        """
        Cancels active speech tasks completely.
        """
        if self._active_task and not self._active_task.done():
            self._active_task.cancel()
        self._paused_text = None
        self._paused_callback = None
        self.is_speaking = False

    def resume(self) -> None:
        """
        Resumes paused voice stream.
        """
        if self._paused_text:
            logger.info("VoiceOutput | Resuming paused speech stream...")
            self.say(self._paused_text, self._paused_callback)

    async def _run_speaking_simulation(self, text: str, callback: Optional[Callable[[], None]] = None) -> None:
        try:
            logger.info(f"VoiceOutput | Speaking: '{text}'")
            # Compute duration based on typical reading speed (18 characters per second)
            duration = max(1.0, len(text) / 18.0)
            # Cap simulated delay to a maximum of 3 seconds for fast test runs
            duration = min(3.0, duration)
            await asyncio.sleep(duration)
            
            logger.info("VoiceOutput | Speech completed successfully.")
            self.is_speaking = False
            if callback:
                if asyncio.iscoroutinefunction(callback):
                    await callback()
                else:
                    callback()
        except asyncio.CancelledError:
            logger.info("VoiceOutput | Speaking simulation task was cancelled.")
            self.is_speaking = False
        except Exception as e:
            logger.error(f"VoiceOutput | Speaking simulation error: {e}")
            self.is_speaking = False
