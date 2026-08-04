import json
import datetime
import shutil
import wave
from pathlib import Path
from loguru import logger

class PackageBuilder:
    def concatenate_wav_files(self, input_paths: list[Path], output_path: Path):
        """
        Concatenates multiple standard WAV files into a single WAV file.
        """
        if not input_paths:
            raise ValueError("No input audio files provided for concatenation.")
        
        logger.info(f"PackageBuilder | Concatenating {len(input_paths)} WAV files to {output_path}")
        
        # Read parameters from the first WAV file
        with wave.open(str(input_paths[0]), "rb") as w_in:
            params = w_in.getparams()
            
        with wave.open(str(output_path), "wb") as w_out:
            w_out.setparams(params)
            for path in input_paths:
                with wave.open(str(path), "rb") as w_in:
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
        slide_audios: dict[int, Path],
        slide_notes: dict[int, str]
    ) -> Path:
        """
        Assembles a package from HR-recorded slides, generating combined narration and timelines.
        """
        logger.info(f"PackageBuilder | Building HR package for session: {session_id}")
        
        # 1. Ensure slide_audio directory exists in session
        slide_audio_pkg_dir = session_dir / "slide_audio"
        slide_audio_pkg_dir.mkdir(parents=True, exist_ok=True)

        # 2. Sort and copy slide audios, measuring durations
        sorted_slide_indices = sorted(slide_audios.keys())
        input_wav_paths = []
        slide_audio_metadata = {}
        current_offset_ms = 0.0
        events = []

        for idx, slide_num in enumerate(sorted_slide_indices):
            src_wav_path = slide_audios[slide_num]
            dest_wav_name = f"slide_{slide_num}.wav"
            dest_wav_path = slide_audio_pkg_dir / dest_wav_name
            
            # Copy to target directory
            shutil.copy(src_wav_path, dest_wav_path)
            input_wav_paths.append(dest_wav_path)
            
            duration_ms = self.get_wav_duration_ms(dest_wav_path)
            notes = slide_notes.get(slide_num, "")
            
            slide_audio_metadata[str(slide_num)] = {
                "filename": dest_wav_name,
                "duration_ms": int(duration_ms),
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
