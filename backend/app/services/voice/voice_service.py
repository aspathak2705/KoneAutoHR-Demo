import os
import json
import re
import wave
import io
from pathlib import Path
from typing import List, Dict, Any, Tuple
from loguru import logger
from app.services.voice.sarvam_client import SarvamClient
from app.services.storage_service import storage_service

class VoiceService:
    def __init__(self):
        # Trigger PydanticSettings loading to populate os.environ with .env key
        from app.core.config import settings
        api_key = os.environ.get("SARVAM_API_KEY", "")
        self.client = SarvamClient(api_key=api_key if api_key else None)

    def _split_into_chunks(self, text: str, max_chars: int = 500) -> List[str]:
        """
        Split a block of text into chunks of at most max_chars without dividing sentences.
        """
        sentences = re.split(r'(?<=[.!?])\s+', text)
        chunks = []
        current_chunk = []
        current_len = 0
        for s in sentences:
            s = s.strip()
            if not s:
                continue
            # If a single sentence exceeds the limit, chunk it by words as fallback
            if len(s) > max_chars:
                if current_chunk:
                    chunks.append(" ".join(current_chunk))
                    current_chunk = []
                    current_len = 0
                words = s.split(" ")
                temp_words = []
                temp_len = 0
                for w in words:
                    if temp_len + len(w) + 1 > max_chars:
                        chunks.append(" ".join(temp_words))
                        temp_words = [w]
                        temp_len = len(w)
                    else:
                        temp_words.append(w)
                        temp_len += len(w) + 1
                if temp_words:
                    current_chunk = temp_words
                    current_len = temp_len
            elif current_len + len(s) + 1 <= max_chars:
                current_chunk.append(s)
                current_len += len(s) + 1
            else:
                chunks.append(" ".join(current_chunk))
                current_chunk = [s]
                current_len = len(s)
        if current_chunk:
            chunks.append(" ".join(current_chunk))
        return chunks

    def _merge_wav_buffers(self, wav_bytes_list: List[bytes]) -> bytes:
        """
        Merge multiple WAV bytes buffers into a single combined WAV buffer.
        """
        if not wav_bytes_list:
            return b""
        
        # Read format parameters from first chunk
        first_io = io.BytesIO(wav_bytes_list[0])
        try:
            with wave.open(first_io, "rb") as w:
                params = w.getparams()
        except Exception as e:
            logger.error(f"VoiceService | Failed to read format params: {e}")
            return wav_bytes_list[0]

        out_io = io.BytesIO()
        try:
            with wave.open(out_io, "wb") as out_w:
                out_w.setparams(params)
                for chunk_bytes in wav_bytes_list:
                    with wave.open(io.BytesIO(chunk_bytes), "rb") as in_w:
                        out_w.writeframes(in_w.readframes(in_w.getnframes()))
            return out_io.getvalue()
        except Exception as e:
            logger.error(f"VoiceService | Failed to merge WAV files: {e}")
            # Fallback to concatenate
            return b"".join(wav_bytes_list)

    async def generate_narration(self, session_id: str, script_payload: dict) -> Tuple[Path, List[Dict[str, Any]], float]:
        """
        Processes the complete script payload, splits sentences/paragraphs into chunks <= 500 chars,
        synthesizes each chunk via Sarvam API, merges the outputs into narration.wav, and
        calculates cumulative timestamps.
        """
        segments = []
        opening = script_payload.get("opening", {})
        welcome_flow = script_payload.get("welcome_flow", {})
        
        # Opening/Greetings mapped to slide 1
        intros = [
            opening.get("greeting") or welcome_flow.get("greeting"),
            opening.get("presenter_intro") or welcome_flow.get("intro"),
            opening.get("employee_welcome"),
            opening.get("audio_check") or welcome_flow.get("audio_check"),
            opening.get("ice_breaker") or welcome_flow.get("ice_breaker"),
            opening.get("session_rules") or welcome_flow.get("rules"),
            opening.get("agenda")
        ]
        for intro in intros:
            if intro:
                if isinstance(intro, list):
                    intro = " ".join(intro)
                segments.append({"slide": 1, "text": intro.strip()})

        # Slides narrations
        slides = script_payload.get("slides")
        if isinstance(slides, list):
            for s in slides:
                slide_num = int(s.get("slide_number", 1))
                parts = [
                    s.get("objective"),
                    s.get("transition_in"),
                    s.get("narration"),
                    s.get("understanding_check"),
                    s.get("transition_out")
                ]
                for p in parts:
                    if p:
                        segments.append({"slide": slide_num, "text": p.strip()})
        else:
            slide_narrations = script_payload.get("slide_narrations", {})
            for num_str, data in slide_narrations.items():
                slide_num = int(num_str)
                narration = data.get("narration", "")
                if narration:
                    segments.append({"slide": slide_num, "text": narration.strip()})

        # Closing segments mapped to the last slide
        last_slide = max([s["slide"] for s in segments]) if segments else 1
        closing = script_payload.get("closing", {})
        closing_script = script_payload.get("closing_script", {})
        closings = [
            closing.get("summary") or closing_script.get("summary"),
            closing.get("next_steps") or closing_script.get("next_steps"),
            closing.get("farewell")
        ]
        for close in closings:
            if close:
                segments.append({"slide": last_slide, "text": close.strip()})

        if not segments:
            segments.append({"slide": 1, "text": "Welcome to the presentation."})

        # Group sentences into <= 500 character chunks per slide
        chunks = []
        for seg in segments:
            slide_num = seg["slide"]
            text_chunks = self._split_into_chunks(seg["text"], max_chars=500)
            for chunk_text in text_chunks:
                if chunk_text.strip():
                    chunks.append({"slide": slide_num, "text": chunk_text})

        # Determine speaker
        voice_tone = script_payload.get("ai_persona", {}).get("tone", "shubh").strip().lower()
        available_speakers = {
            "anushka", "abhilash", "manisha", "vidya", "arya", "karun", "hitesh", "aditya",
            "ritu", "priya", "neha", "rahul", "pooja", "rohan", "simran", "kavya", "amit",
            "dev", "ishita", "shreya", "ratan", "varun", "manan", "sumit", "roopa", "kabir",
            "aayan", "shubh", "ashutosh", "advait", "anand", "tanya", "tarun", "sunny",
            "mani", "gokul", "vijay", "shruti", "suhani", "mohit", "kavitha", "rehan",
            "soham", "rupali"
        }
        if voice_tone not in available_speakers:
            logger.warning(f"VoiceService | Speaker '{voice_tone}' is not recognized. Defaulting to 'shubh'.")
            voice_tone = "shubh"

        logger.info(f"VoiceService | Generating {len(chunks)} speech chunks using speaker: {voice_tone}...")
        
        # Sequentially call Sarvam TTS API for each chunk
        wav_buffers = []
        timestamps = []
        accumulated_time_ms = 0.0
        current_slide = None

        for idx, chunk in enumerate(chunks):
            slide_num = chunk["slide"]
            chunk_text = chunk["text"]
            
            logger.info(f"VoiceService | Synthesizing chunk {idx+1}/{len(chunks)} for Slide {slide_num} ({len(chunk_text)} chars)...")
            chunk_audio = await self.client.text_to_speech(chunk_text, voice=voice_tone)
            duration_sec = self.client.get_audio_duration(chunk_audio)
            
            wav_buffers.append(chunk_audio)

            # Record slide transition timestamp when slide changes
            if current_slide is None or slide_num > current_slide:
                timestamps.append({
                    "slide": slide_num,
                    "time_ms": int(round(accumulated_time_ms))
                })
                current_slide = slide_num

            accumulated_time_ms += duration_sec * 1000.0

        # Merge WAV buffers
        logger.info("VoiceService | Merging audio chunks into single presentation narration.wav...")
        merged_audio = self._merge_wav_buffers(wav_buffers)
        total_duration = self.client.get_audio_duration(merged_audio)
        duration_ms = total_duration * 1000.0
        
        # Save output narration.wav file to session dir
        session_dir = storage_service.get_session_dir(session_id)
        session_dir.mkdir(parents=True, exist_ok=True)
        audio_path = session_dir / "narration.wav"
        with open(audio_path, "wb") as f:
            f.write(merged_audio)

        logger.info(f"VoiceService | Synthesized narration successfully. Total duration: {total_duration:.2f}s ({duration_ms:.0f}ms)")
        return audio_path, timestamps, duration_ms

voice_service = VoiceService()
