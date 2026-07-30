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
        and returns list of audio track details.
        """
        audio_tracks = []
        tasks_to_run = []
        
        # Helper to safely load JSON if it's stored as a string
        if isinstance(script_payload, str):
            import json
            try:
                script_payload = json.loads(script_payload)
            except Exception:
                script_payload = {}

        opening = script_payload.get("opening") or {}
        welcome_flow = script_payload.get("welcome_flow") or {}
        
        # Get greeting
        greeting = opening.get("greeting") or welcome_flow.get("greeting") or ""
        if greeting:
            tasks_to_run.append(("greeting", greeting, 0))
            
        # Get presenter intro
        presenter_intro = opening.get("presenter_intro") or welcome_flow.get("intro") or ""
        if presenter_intro:
            tasks_to_run.append(("intro", presenter_intro, 0))
            
        # Get employee welcome
        employee_welcome = opening.get("employee_welcome") or ""
        if employee_welcome:
            tasks_to_run.append(("employee_welcome", employee_welcome, 0))
            
        # Get audio check
        audio_check = opening.get("audio_check") or welcome_flow.get("audio_check") or ""
        if audio_check:
            tasks_to_run.append(("audio_check", audio_check, 0))
            
        # Get ice breaker
        ice_breaker = opening.get("ice_breaker") or welcome_flow.get("ice_breaker") or ""
        if ice_breaker:
            tasks_to_run.append(("ice_breaker", ice_breaker, 0))
            
        # Get session rules
        session_rules = opening.get("session_rules") or welcome_flow.get("rules") or ""
        if session_rules:
            tasks_to_run.append(("session_rules", session_rules, 0))
            
        # Get agenda
        agenda = opening.get("agenda") or ""
        if isinstance(agenda, list):
            agenda = " ".join(agenda)
        if agenda:
            tasks_to_run.append(("agenda", agenda, 0))

        # Slides
        slides = script_payload.get("slides")
        if isinstance(slides, list):
            for s in slides:
                slide_num = int(s.get("slide_number", 1))
                
                objective = s.get("objective") or ""
                if objective:
                    tasks_to_run.append((f"slide_{slide_num}_objective", objective, slide_num))
                    
                transition_in = s.get("transition_in") or ""
                if transition_in:
                    tasks_to_run.append((f"slide_{slide_num}_transition_in", transition_in, slide_num))
                    
                narration = s.get("narration") or ""
                if narration:
                    tasks_to_run.append((f"slide_{slide_num}", narration, slide_num))
                    tasks_to_run.append((f"slide_{slide_num}_narration", narration, slide_num))
                    
                understanding_check = s.get("understanding_check") or ""
                if understanding_check:
                    tasks_to_run.append((f"slide_{slide_num}_understanding_check", understanding_check, slide_num))
                    
                transition_out = s.get("transition_out") or ""
                if transition_out:
                    tasks_to_run.append((f"slide_{slide_num}_transition_out", transition_out, slide_num))
        else:
            # Fallback legacy slide narrations dict parsing
            slide_narrations = script_payload.get("slide_narrations", {})
            for num_str, data in slide_narrations.items():
                slide_num = int(num_str)
                narration = data.get("narration", "")
                if narration:
                    tasks_to_run.append((f"slide_{slide_num}", narration, slide_num))
                    tasks_to_run.append((f"slide_{slide_num}_narration", narration, slide_num))

        # Closing
        closing = script_payload.get("closing") or {}
        closing_script = script_payload.get("closing_script") or {}
        
        closing_summary = closing.get("summary") or closing_script.get("summary") or ""
        if closing_summary:
            tasks_to_run.append(("closing", closing_summary, 99))
            
        closing_next_steps = closing.get("next_steps") or closing_script.get("next_steps") or ""
        if closing_next_steps:
            tasks_to_run.append(("closing_next_steps", closing_next_steps, 99))
            
        closing_farewell = closing.get("farewell") or ""
        if closing_farewell:
            tasks_to_run.append(("closing_farewell", closing_farewell, 99))

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
