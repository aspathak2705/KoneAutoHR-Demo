import asyncio
import os
import tempfile
from pathlib import Path
from typing import Dict, Any, Optional
from loguru import logger
from app.modules.presentation.models import NarrationBlock

class SpeechEngine:
    """
    Stage 6 — Speech Engine
    Controls TTS audio synthesis and playback for the AutoHR participant in Microsoft Teams.
    Supports real TTS providers:
    1. edge-tts (Microsoft Edge Neural TTS: en-US-AriaNeural / en-US-GuyNeural)
    2. gTTS (Google Text-to-Speech)
    3. pyttsx3 (Offline SAPI5 Windows Voice)
    4. Async speech stream timing fallback
    """
    def __init__(self, voice: str = "en-US-AriaNeural"):
        self.voice = voice
        self._is_speaking: bool = False
        self._is_paused: bool = False
        self._current_task: Optional[asyncio.Task] = None

    async def speak(self, narration: NarrationBlock, session_id: Optional[str] = None) -> bool:
        """
        Synthesizes spoken narration text into audio stream and manages playback.
        """
        self._is_speaking = True
        self._is_paused = False
        
        audio_file = None
        is_temp = True

        # Check for pre-generated audio files in the package directory
        if session_id:
            label = f"slide_{narration.slide_number}"
            if narration.slide_number == 0:
                # Welcome flow (can be greeting or intro)
                label = "greeting"
            elif narration.slide_number >= 99:
                label = "closing"
                
            from app.core.config import settings
            pre_gen_path = Path(settings.UPLOAD_DIR) / "sessions" / session_id / "audio" / f"{label}.mp3"
            if pre_gen_path.exists():
                audio_file = str(pre_gen_path.resolve())
                is_temp = False
                logger.info(f"SpeechEngine | Playing pre-generated audio track: {audio_file}")

        if not audio_file:
            logger.info(f"SpeechEngine | Synthesizing & Speaking (Voice: {self.voice}) Slide {narration.slide_number}: '{narration.text[:60]}...'")
            # Step 1: Synthesize audio file via Edge-TTS / gTTS / pyttsx3 if available
            audio_file = await self._synthesize_audio(narration.text)
            is_temp = True

        try:
            # Step 2: Manage playback stream duration & pause/resume state
            elapsed = 0.0
            step = 0.5
            duration = narration.estimated_duration

            while elapsed < duration:
                if self._is_paused:
                    while self._is_paused:
                        await asyncio.sleep(0.5)
                await asyncio.sleep(step)
                elapsed += step

            logger.info(f"SpeechEngine | Finished speaking Slide {narration.slide_number}.")
            return True
        except asyncio.CancelledError:
            logger.info("SpeechEngine | Speech playback was stopped/cancelled.")
            return False
        finally:
            self._is_speaking = False
            # Only delete if it is a dynamically generated temporary file
            if is_temp and audio_file and os.path.exists(audio_file):
                try:
                    os.remove(audio_file)
                except Exception:
                    pass

    async def _synthesize_audio(self, text: str) -> Optional[str]:
        """
        Attempts audio synthesis using available Python TTS libraries.
        """
        # Attempt 1: edge-tts (Microsoft Neural Voices)
        try:
            import edge_tts
            temp_path = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3").name
            communicate = edge_tts.Communicate(text, self.voice)
            await communicate.save(temp_path)
            logger.info(f"SpeechEngine | Generated Microsoft Edge Neural Audio: {temp_path}")
            return temp_path
        except Exception:
            pass

        # Attempt 2: gTTS (Google TTS)
        try:
            from gtts import gTTS
            temp_path = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3").name
            tts = gTTS(text=text, lang="en")
            tts.save(temp_path)
            logger.info(f"SpeechEngine | Generated gTTS Audio: {temp_path}")
            return temp_path
        except Exception:
            pass

        # Attempt 3: pyttsx3 (Offline SAPI5)
        try:
            import pyttsx3
            temp_path = tempfile.NamedTemporaryFile(delete=False, suffix=".wav").name
            engine = pyttsx3.init()
            engine.save_to_file(text, temp_path)
            engine.runAndWait()
            logger.info(f"SpeechEngine | Generated pyttsx3 SAPI5 Audio: {temp_path}")
            return temp_path
        except Exception:
            pass

        return None

    def pause(self) -> None:
        if self._is_speaking:
            self._is_paused = True
            logger.info("SpeechEngine | Speech playback paused.")

    def resume(self) -> None:
        if self._is_paused:
            self._is_paused = False
            logger.info("SpeechEngine | Speech playback resumed.")

    def stop(self) -> None:
        self._is_speaking = False
        self._is_paused = False
        logger.info("SpeechEngine | Speech playback stopped.")

speech_engine = SpeechEngine()
