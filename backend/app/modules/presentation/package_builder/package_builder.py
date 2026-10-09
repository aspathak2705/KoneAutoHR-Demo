import json
import datetime
import shutil
import wave
from pathlib import Path
from typing import Optional, Dict, List, Any
from loguru import logger

class PackageBuilder:
    def get_wav_params(self, file_path: Path):
        """
        Reads and returns wave file parameters.
        """
        with wave.open(str(file_path), "rb") as w:
            return w.getparams()

    def generate_silence_wav(
        self,
        output_path: Path,
        duration_ms: int = 5000,
        sample_rate: int = 44100,
        num_channels: int = 2,
        sample_width: int = 2
    ) -> Path:
        """
        Generates a valid PCM WAV file containing digital silence for the exact duration.
        """
        num_frames = int((duration_ms / 1000.0) * sample_rate)
        frame_bytes = b"\x00" * (num_channels * sample_width)
        silence_data = frame_bytes * num_frames
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(output_path), "wb") as w_out:
            w_out.setnchannels(num_channels)
            w_out.setsampwidth(sample_width)
            w_out.setframerate(sample_rate)
            w_out.writeframes(silence_data)
            
        return output_path

    def concatenate_wav_files(self, input_paths: list[Path], output_path: Path):
        """
        Concatenates multiple standard WAV files into a single WAV file with parameter validation.
        """
        if not input_paths:
            raise ValueError("No input audio files provided for concatenation.")
        
        logger.info(f"PackageBuilder | Concatenating {len(input_paths)} WAV files to {output_path}")
        
        # Read parameters from the first WAV file
        with wave.open(str(input_paths[0]), "rb") as w_in:
            ref_params = w_in.getparams()
            
        with wave.open(str(output_path), "wb") as w_out:
            w_out.setparams(ref_params)
            for path in input_paths:
                with wave.open(str(path), "rb") as w_in:
                    curr_params = w_in.getparams()
                    if (curr_params.nchannels != ref_params.nchannels or 
                        curr_params.sampwidth != ref_params.sampwidth or 
                        curr_params.framerate != ref_params.framerate):
                        logger.warning(
                            f"PackageBuilder | Parameter mismatch in {path.name}: "
                            f"{curr_params} vs ref {ref_params}"
                        )
                    # Write frames
                    w_out.writeframes(w_in.readframes(w_in.getnframes()))

    def get_wav_duration_ms(self, file_path: Path) -> float:
        """
        Parses wave file header to return exact duration in milliseconds.
        """
        try:
            with wave.open(str(file_path), "rb") as w:
                frames = w.getnframes()
                rate = w.getframerate()
                if rate > 0:
                    return (frames / float(rate)) * 1000.0
        except Exception as e:
            logger.error(f"PackageBuilder | Failed to read WAV duration for {file_path.name}: {e}")
        return 0.0

    def build_hr_package(
        self,
        session_id: str,
        session_dir: Path,
        presentation_filename: str,
        slide_count: int,
        slide_audios: dict[int, Optional[Path]],
        slide_notes: dict[int, str],
        slide_types: Optional[dict[int, str]] = None
    ) -> Path:
        """
        Assembles a package from HR-recorded slides, generating combined narration and timelines.
        Supports explicit SILENT slides with 5-second digital silence hold.
        """
        logger.info(f"PackageBuilder | Building HR package for session: {session_id}")
        slide_types = slide_types or {}
        
        # 1. Ensure slide_audio directory exists in session
        slide_audio_pkg_dir = session_dir / "slide_audio"
        slide_audio_pkg_dir.mkdir(parents=True, exist_ok=True)

        # Determine reference audio parameters from first available real audio file
        ref_rate = 44100
        ref_channels = 2
        ref_sampwidth = 2
        for s_idx in sorted(slide_audios.keys()):
            audio_p = slide_audios[s_idx]
            if audio_p and audio_p.exists() and slide_types.get(s_idx) != "SILENT":
                try:
                    params = self.get_wav_params(audio_p)
                    ref_rate = params.framerate
                    ref_channels = params.nchannels
                    ref_sampwidth = params.sampwidth
                    break
                except Exception:
                    pass

        # 2. Sort and prepare slide audios, measuring durations
        sorted_slide_indices = sorted(slide_audios.keys())
        input_wav_paths = []
        slide_audio_metadata = {}
        current_offset_ms = 0.0
        events = []

        for idx, slide_num in enumerate(sorted_slide_indices):
            is_silent = slide_types.get(slide_num) == "SILENT" or slide_audios[slide_num] is None
            
            if is_silent:
                dest_wav_name = f"slide_{slide_num}_silent.wav"
                dest_wav_path = slide_audio_pkg_dir / dest_wav_name
                self.generate_silence_wav(
                    output_path=dest_wav_path,
                    duration_ms=5000,
                    sample_rate=ref_rate,
                    num_channels=ref_channels,
                    sample_width=ref_sampwidth
                )
                duration_ms = 5000.0
                is_type = "SILENT"
            else:
                src_wav_path = slide_audios[slide_num]
                dest_wav_name = f"slide_{slide_num}.wav"
                dest_wav_path = slide_audio_pkg_dir / dest_wav_name
                shutil.copy(src_wav_path, dest_wav_path)
                duration_ms = self.get_wav_duration_ms(dest_wav_path)
                is_type = "AUDIO"

            input_wav_paths.append(dest_wav_path)
            notes = slide_notes.get(slide_num, "")
            
            slide_audio_metadata[str(slide_num)] = {
                "filename": dest_wav_name,
                "duration_ms": int(duration_ms),
                "type": is_type,
                "notes": notes
            }
            
            # Append timeline event
            events.append({
                "id": idx + 1,
                "time_ms": int(current_offset_ms),
                "action": "goto_slide",
                "slide": slide_num
            })
            
            current_offset_ms += duration_ms

        # 3. Concatenate wav files into single narration.wav
        narration_path = session_dir / "narration.wav"
        self.concatenate_wav_files(input_wav_paths, narration_path)
        
        # 4. Generate presentation_timeline.json
        timeline_data = {
            "version": "1.0",
            "duration_ms": int(current_offset_ms),
            "events": events
        }
        timeline_path = session_dir / "presentation_timeline.json"
        with open(timeline_path, "w", encoding="utf-8") as f:
            json.dump(timeline_data, f, indent=2)

        # 5. Generate rich manifest.json
        manifest_data = {
            "version": "1.0",
            "presentation": presentation_filename,
            "audio": "narration.wav",
            "timeline": "presentation_timeline.json",
            "duration_ms": int(current_offset_ms),
            "slides": int(slide_count),
            "creation_mode": "HR",
            "package_version": "1.0.0",
            "created_time": datetime.datetime.utcnow().isoformat() + "Z",
            "timeline_version": "1.0",
            "slide_audio_metadata": slide_audio_metadata
        }
        manifest_path = session_dir / "manifest.json"
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest_data, f, indent=2)

        # 6. Generate compatibility file induction_package.json so readiness validates
        induction_package_path = session_dir / "induction_package.json"
        compat_package = {
            "session_metadata": {
                "session_id": session_id,
                "name": "HR Recorded Session",
                "language": "en-IN",
                "session_type": "HR_RECORDED",
                "prepared_at": datetime.datetime.utcnow().isoformat()
            },
            "meeting_context": {},
            "ai_persona": {},
            "employee_profiles": [],
            "welcome_flow": {
                "greeting": "Welcome to the KONE HR presentation.",
                "wait_message": "Please wait, the presentation will start shortly.",
                "audio_check": "Audio test successful.",
                "ice_breaker": "",
                "agenda": [],
                "meeting_join_message": "",
                "late_joiner_message": "",
                "start_confirmation": ""
            },
            "slide_narrations": {
                f"slide_{s_num}": {
                    "slide_number": s_num,
                    "narration": meta["notes"]
                }
                for s_num, meta in slide_audio_metadata.items()
            },
            "faq": [],
            "closing_script": {},
            "audio_metadata": [
                {
                    "filename": "narration.wav",
                    "duration": current_offset_ms / 1000.0,
                    "checksum": ""
                }
            ]
        }
        with open(induction_package_path, "w", encoding="utf-8") as f:
            json.dump(compat_package, f, indent=2)

        logger.info(f"PackageBuilder | Successfully built HR Recorded package at: {session_dir}")
        return manifest_path

package_builder = PackageBuilder()
