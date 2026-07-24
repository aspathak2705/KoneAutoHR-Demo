import asyncio
from typing import Callable, Optional
from loguru import logger

class VoiceOutputInterface:
    def say(self, text: str, callback: Optional[Callable[[], None]] = None, audio_file: Optional[str] = None) -> None:
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
    def __init__(self, session_id: str = "default_session"):
        self.session_id = session_id
        self._active_task: Optional[asyncio.Task] = None
        self._paused_text: Optional[str] = None
        self._paused_callback: Optional[Callable[[], None]] = None
        self.is_speaking: bool = False

    def say(self, text: str, callback: Optional[Callable[[], None]] = None, audio_file: Optional[str] = None) -> None:
        """
        Plays actual audio file if available; otherwise runs simulated voice delay.
        """
        self.stop()
        self.is_speaking = True
        self._active_task = asyncio.create_task(
            self._run_speaking(text, callback, audio_file)
        )

    def interrupt(self) -> None:
        """
        Interrupts speech playback and stores state for potential resuming.
        """
        if self._active_task and not self._active_task.done():
            self._active_task.cancel()
            self._paused_text = "Remaining text stream content..."
            logger.info(f"VoiceOutput | Session: {self.session_id} | Voice playback interrupted.")
        self.is_speaking = False
        
        # Stop actual audio playback if active
        from app.modules.meeting_bot.media.audio_controller import cleanup_audio_controller
        cleanup_audio_controller(self.session_id)

    def stop(self) -> None:
        """
        Cancels active speech tasks completely.
        """
        if self._active_task and not self._active_task.done():
            self._active_task.cancel()
        self._paused_text = None
        self._paused_callback = None
        self.is_speaking = False
        
        # Stop actual audio playback if active
        from app.modules.meeting_bot.media.audio_controller import cleanup_audio_controller
        cleanup_audio_controller(self.session_id)

    def resume(self) -> None:
        """
        Resumes paused voice stream.
        """
        if self._paused_text:
            logger.info(f"VoiceOutput | Session: {self.session_id} | Resuming paused speech stream...")
            self.say(self._paused_text, self._paused_callback)

    async def _run_speaking(self, text: str, callback: Optional[Callable[[], None]] = None, audio_file: Optional[str] = None) -> None:
        try:
            logger.info(f"VoiceOutput | Session: {self.session_id} | Speaking: '{text[:60]}...'")
            
            played_real = False
            if audio_file:
                from app.modules.meeting_bot.media.audio_controller import get_audio_controller
                audio_ctrl = get_audio_controller(self.session_id)
                try:
                    audio_ctrl.play_audio(audio_file)
                    if audio_ctrl.process:
                        played_real = True
                        while audio_ctrl.process.poll() is None:
                            await asyncio.sleep(0.2)
                        logger.info(f"VoiceOutput | Finished playing real audio track: {audio_file}")
                except Exception as e:
                    logger.warning(f"VoiceOutput | Session: {self.session_id} | Real audio play failed: {e}. Simulating instead.")
            
            if not played_real:
                # Compute duration based on typical reading speed (18 characters per second)
                duration = max(1.0, len(text) / 18.0)
                # Cap simulated delay to a maximum of 3 seconds for fast test runs
                duration = min(3.0, duration)
                await asyncio.sleep(duration)
                logger.info(f"VoiceOutput | Session: {self.session_id} | Speech simulation completed successfully.")

            self.is_speaking = False
            if callback:
                if asyncio.iscoroutinefunction(callback):
                    await callback()
                else:
                    callback()
        except asyncio.CancelledError:
            logger.info(f"VoiceOutput | Session: {self.session_id} | Speaking task was cancelled.")
            from app.modules.meeting_bot.media.audio_controller import cleanup_audio_controller
            cleanup_audio_controller(self.session_id)
            self.is_speaking = False
        except Exception as e:
            logger.error(f"VoiceOutput | Session: {self.session_id} | Speaking error: {e}")
            self.is_speaking = False
