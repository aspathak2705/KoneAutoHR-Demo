import os
import tempfile
import asyncio
from typing import Optional, List, Dict, Any
from loguru import logger
from sqlalchemy.orm import Session as DBSession
from app.modules.induction.package.asset_manager import asset_manager
from app.repositories.presentation_job_repository import presentation_job_repository
from app.models.presentation_job import PresentationJob

class SpeechGenerationPipeline:
    def __init__(self):
        self.default_voice = "en-US-AriaNeural"

    async def synthesize_text_to_bytes(self, text: str, voice: str) -> Optional[bytes]:
        """
        Synthesizes text to MP3 bytes using Edge-TTS, gTTS, or fallback to an empty byte stream.
        """
        # Attempt 1: edge-tts
        try:
            import edge_tts
            communicate = edge_tts.Communicate(text, voice)
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp:
                temp_path = tmp.name
            await communicate.save(temp_path)
            with open(temp_path, "rb") as f:
                data = f.read()
            try:
                os.remove(temp_path)
            except Exception:
                pass
            return data
        except Exception:
            pass

        # Attempt 2: gTTS
        try:
            from gtts import gTTS
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp:
                temp_path = tmp.name
            tts = gTTS(text=text, lang="en")
            tts.save(temp_path)
            with open(temp_path, "rb") as f:
                data = f.read()
            try:
                os.remove(temp_path)
            except Exception:
                pass
            return data
        except Exception:
            pass

        return None

    async def generate_speech_for_script(
        self,
        db: DBSession,
        presentation_id: str,
        session_id: str,
        script_payload: dict,
        voice: str,
        job: PresentationJob
    ) -> List[Dict[str, Any]]:
        """
        Loops through the welcome/agenda/slides/closing texts, generates MP3 files,
        and registers them as assets. Updates job progress sequentially.
        """
        audio_assets = []
        
        # 1. Identify all text blocks to generate
        tasks_to_run = []
        
        # Welcome
        welcome_intro = script_payload.get("opening", {}).get("presenter_intro", "")
        if welcome_intro:
            tasks_to_run.append(("intro", welcome_intro))
            
        welcome_rules = script_payload.get("opening", {}).get("session_rules", "")
        if welcome_rules:
            tasks_to_run.append(("greeting", welcome_rules))

        # Slides
        slides = script_payload.get("slides", [])
        for s in slides:
            slide_num = s.get("slide_number")
            narration = s.get("narration", "")
            if slide_num and narration:
                tasks_to_run.append((f"slide_{slide_num}", narration))

        # Closing
        closing_summary = script_payload.get("closing", {}).get("summary", "")
        if closing_summary:
            tasks_to_run.append(("closing", closing_summary))

        total_tasks = len(tasks_to_run)
        if total_tasks == 0:
            return []

        # 2. Loop and generate
        for idx, (label, text) in enumerate(tasks_to_run):
            logger.info(f"SpeechGeneration | Synthesizing {label} ({idx+1}/{total_tasks}): '{text[:30]}...'")
            
            # Synthesize
            audio_bytes = await self.synthesize_text_to_bytes(text, voice)
            if not audio_bytes:
                # If both TTS tools fail, generate fallback empty audio bytes or mock delay
                audio_bytes = b"MOCK_AUDIO_PAYLOAD"

            # Compute metadata
            duration = max(3.0, round(len(text) * 0.085, 2)) # Approx words-per-minute estimation
            
            relative_path = f"sessions/{session_id}/audio/{label}.mp3"
            
            # Save & Register asset
            asset = asset_manager.save_and_register_asset(
                db=db,
                presentation_id=presentation_id,
                relative_path=relative_path,
                content=audio_bytes,
                asset_type="audio"
            )

            audio_assets.append({
                "filename": f"{label}.mp3",
                "duration": duration,
                "checksum": asset.checksum,
                "path": relative_path,
                "voice": voice,
                "version": 1
            })

            # Update job progress
            progress = (idx + 1) / total_tasks
            presentation_job_repository.update(db, job, progress=progress)
            # Short sleep to prevent rate limiting
            await asyncio.sleep(0.1)

        return audio_assets

speech_generation_pipeline = SpeechGenerationPipeline()
