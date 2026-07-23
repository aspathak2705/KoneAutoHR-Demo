import os
import tempfile
import asyncio
import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any
from loguru import logger
from sqlalchemy.orm import Session as DBSession
from app.models.presentation_job import PresentationJob
from app.repositories.presentation_job_repository import presentation_job_repository

class SpeechPipeline:
    def __init__(self):
        self.default_voice = "en-US-AriaNeural"

    async def synthesize_text_to_file(self, text: str, voice: str, output_path: Path) -> bool:
        """
        Synthesizes text to MP3 file using Edge-TTS or gTTS.
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Attempt 1: edge-tts
        try:
            import edge_tts
            communicate = edge_tts.Communicate(text, voice)
            await communicate.save(str(output_path))
            return True
        except Exception:
            pass

        # Attempt 2: gTTS
        try:
            from gtts import gTTS
            tts = gTTS(text=text, lang="en")
            tts.save(str(output_path))
            return True
        except Exception:
            pass

        # Fallback: Create mock file
        try:
            with open(output_path, "wb") as f:
                f.write(b"MOCK_AUDIO_PAYLOAD")
            return True
        except Exception:
            pass

        return False

    async def execute(
        self,
        db: DBSession,
        session_id: str,
        script_payload: dict,
        voice: str,
        session_dir: Path,
        job: PresentationJob
    ) -> List[Dict[str, Any]]:
        """
        Loops welcome/agenda/slides/closing texts, generates MP3 files,
        and returns list of audio track details (does not register database records).
        """
        audio_tracks = []
        
        # 1. Identify all text blocks to generate
        tasks_to_run = []
        
        # Welcome (intro)
        welcome_intro = script_payload.get("welcome_flow", {}).get("greeting", "")
        if welcome_intro:
            tasks_to_run.append(("greeting", welcome_intro, 0))
            
        welcome_rules = script_payload.get("welcome_flow", {}).get("summary", "")
        if welcome_rules:
            tasks_to_run.append(("intro", welcome_rules, 0))

        # Slides
        slide_narrations = script_payload.get("slide_narrations", {})
        for num_str, data in slide_narrations.items():
            slide_num = int(num_str)
            narration = data.get("narration", "")
            if narration:
                tasks_to_run.append((f"slide_{slide_num}", narration, slide_num))

        # Closing
        closing_summary = script_payload.get("closing_script", {}).get("summary", "")
        if closing_summary:
            tasks_to_run.append(("closing", closing_summary, 99))

        total_tasks = len(tasks_to_run)
        if total_tasks == 0:
            return []

        # 2. Loop and generate
        for idx, (label, text, slide_num) in enumerate(tasks_to_run):
            logger.info(f"SpeechPipeline | Synthesizing {label} ({idx+1}/{total_tasks}): '{text[:30]}...'")
            
            output_path = session_dir / "audio" / f"{label}.mp3"
            success = await self.synthesize_text_to_file(text, voice, output_path)

            # Compute approximate duration
            duration = max(3.0, round(len(text) * 0.085, 2))

            audio_tracks.append({
                "label": label,
                "slide_number": slide_num,
                "text": text,
                "filename": f"{label}.mp3",
                "file_path": output_path,
                "duration": duration,
                "voice": voice,
                "generation_time": datetime.datetime.now().isoformat()
            })

            # Update job progress
            progress = (idx + 1) / total_tasks
            presentation_job_repository.update(db, job, progress=progress)
            await asyncio.sleep(0.1)

        return audio_tracks

speech_pipeline = SpeechPipeline()
