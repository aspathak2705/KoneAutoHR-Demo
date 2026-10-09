import json
import datetime
import math
import shutil
import wave
from pathlib import Path
from typing import Optional, Dict, List, Any
import numpy as np
import soundfile as sf
from scipy.signal import resample_poly
from loguru import logger

CANONICAL_RATE = 44100
CANONICAL_CHANNELS = 2
CANONICAL_SAMPWIDTH = 2  # 16-bit PCM

class PackageBuilder:
    def get_wav_params(self, file_path: Path):
        """
        Reads and returns wave file parameters.
        """
        with wave.open(str(file_path), "rb") as w:
            return w.getparams()

    def convert_to_canonical_wav(
        self,
        src_path: Path,
        dst_wav_path: Path,
        target_sr: int = CANONICAL_RATE,
        target_ch: int = CANONICAL_CHANNELS
    ) -> float:
        """
        Decodes any supported audio format (MP3, WAV, etc.) via soundfile, converts to canonical
        PCM WAV (16-bit, 44100Hz, stereo), writes to dst_wav_path, and returns exact duration in ms.
        Rejects empty or corrupted audio files.
        """
        if not src_path.exists():
            raise FileNotFoundError(f"Source audio file not found: {src_path}")
        if src_path.stat().st_size == 0:
            raise ValueError(f"Audio file is empty: {src_path.name}")

        try:
            data, sr = sf.read(str(src_path), dtype="float32")
        except Exception as e:
            logger.error(f"PackageBuilder | Failed to decode audio file {src_path.name}: {e}")
            raise ValueError(f"Corrupted or unsupported audio file {src_path.name}: {str(e)}")

        if data.size == 0:
            raise ValueError(f"Audio file contains no playable samples: {src_path.name}")

        # Enforce target channels (stereo)
        if data.ndim == 1:
            data = np.column_stack([data, data])
        elif data.ndim == 2:
            if data.shape[1] == 1:
                data = np.column_stack([data[:, 0], data[:, 0]])
            elif data.shape[1] > target_ch:
                data = data[:, :target_ch]

        # Resample to canonical sample rate (44100Hz) if needed
        if sr != target_sr:
            gcd = math.gcd(sr, target_sr)
            up = target_sr // gcd
            down = sr // gcd
            data = resample_poly(data, up, down, axis=0)

        dst_wav_path.parent.mkdir(parents=True, exist_ok=True)
        sf.write(str(dst_wav_path), data, target_sr, subtype="PCM_16", format="WAV")

        # Calculate exact duration in ms from frame count
        duration_ms = (len(data) / float(target_sr)) * 1000.0
        return duration_ms

    def generate_silence_wav(
        self,
        output_path: Path,
        duration_ms: int = 5000,
        sample_rate: int = CANONICAL_RATE,
        num_channels: int = CANONICAL_CHANNELS,
        sample_width: int = CANONICAL_SAMPWIDTH
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
        Concatenates multiple canonical WAV files into a single WAV file with parameter validation.
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

    def get_audio_duration_ms(self, file_path: Path) -> float:
        """
        Returns exact duration in milliseconds for WAV or MP3 files using soundfile header metadata.
        Falls back to wave.open if applicable.
        """
        try:
            info = sf.info(str(file_path))
            if info.duration > 0:
                return float(info.duration * 1000.0)
        except Exception:
            pass

        try:
            with wave.open(str(file_path), "rb") as w:
                frames = w.getnframes()
                rate = w.getframerate()
                if rate > 0:
                    return (frames / float(rate)) * 1000.0
        except Exception as e:
            logger.error(f"PackageBuilder | Failed to read audio duration for {file_path.name}: {e}")
        return 0.0

    def get_wav_duration_ms(self, file_path: Path) -> float:
        """
        Parses wave or audio file to return exact duration in milliseconds.
        """
        return self.get_audio_duration_ms(file_path)

    def build_hr_package(
        self,
        session_id: str,
        session_dir: Path,
        presentation_filename: str,
        slide_count: int,
        slide_audios: dict[int, Optional[Path]],
        slide_notes: dict[int, str],
        slide_types: Optional[dict[int, str]] = None,
        slide_groups: Optional[dict[int, dict]] = None
    ) -> Path:
        """
        Assembles a package from HR-recorded slides, generating combined narration and timelines.
        Supports explicit SILENT slides with 5-second digital silence hold.
        Supports multi-slide continuous grouped narration across consecutive slides.
        """
        logger.info(f"PackageBuilder | Building HR package for session: {session_id}")
        slide_types = slide_types or {}
        slide_groups = slide_groups or {}
        
        # 1. Ensure slide_audio directory exists in session
        slide_audio_pkg_dir = session_dir / "slide_audio"
        slide_audio_pkg_dir.mkdir(parents=True, exist_ok=True)

        # Determine reference audio parameters from first available real audio file
        ref_rate = CANONICAL_RATE
        ref_channels = CANONICAL_CHANNELS
        ref_sampwidth = CANONICAL_SAMPWIDTH

        # 2. Sort and prepare slide audios, converting to canonical WAV and measuring durations
        sorted_slide_indices = sorted(slide_audios.keys())
        input_wav_paths = []
        slide_audio_metadata = {}
        current_offset_ms = 0.0
        events = []

        for idx, slide_num in enumerate(sorted_slide_indices):
            s_type = slide_types.get(slide_num, "AUDIO")

            if s_type == "GROUP_LINKED":
                # Linked slide in continuous group: audio handled by master slide
                # Do NOT append audio or advance timeline offset here (handled when master processed)
                notes = slide_notes.get(slide_num, "")
                group_info = slide_groups.get(slide_num, {})
                slide_audio_metadata[str(slide_num)] = {
                    "filename": None,
                    "duration_ms": group_info.get("duration_ms", 0),
                    "type": "GROUP_LINKED",
                    "group_id": group_info.get("group_id"),
                    "master_slide": group_info.get("master_slide"),
                    "notes": notes
                }
                continue

            elif s_type == "GROUP_MASTER":
                # Master slide of continuous group
                src_audio_path = slide_audios[slide_num]
                dest_wav_name = f"slide_{slide_num}_group.wav"
                dest_wav_path = slide_audio_pkg_dir / dest_wav_name

                # Canonicalize audio (decode MP3/WAV to 44.1kHz stereo PCM 16-bit)
                total_duration_ms = self.convert_to_canonical_wav(src_audio_path, dest_wav_path)
                input_wav_paths.append(dest_wav_path)

                group_info = slide_groups.get(slide_num, {})
                group_slides = group_info.get("group_slides", [slide_num])
                n_slides = len(group_slides)

                # Distribute duration across slides if not explicitly defined
                custom_durations = group_info.get("slide_durations_ms", {})
                allocated_durations = {}
                if custom_durations and all(s in custom_durations for s in group_slides):
                    allocated_durations = custom_durations
                else:
                    per_slide_ms = int(total_duration_ms / n_slides)
                    for i, g_s in enumerate(group_slides):
                        if i == n_slides - 1:
                            allocated_durations[g_s] = int(total_duration_ms) - (per_slide_ms * (n_slides - 1))
                        else:
                            allocated_durations[g_s] = per_slide_ms

                # Record master metadata
                notes = slide_notes.get(slide_num, "")
                slide_audio_metadata[str(slide_num)] = {
                    "filename": dest_wav_name,
                    "duration_ms": int(total_duration_ms),
                    "type": "GROUP_MASTER",
                    "group_id": group_info.get("group_id"),
                    "group_slides": group_slides,
                    "slide_durations_ms": allocated_durations,
                    "notes": notes
                }

                # Emit timeline events for master slide and all linked slides
                group_cursor_ms = current_offset_ms
                for g_s in group_slides:
                    events.append({
                        "id": len(events) + 1,
                        "time_ms": int(group_cursor_ms),
                        "action": "goto_slide",
                        "slide": g_s
                    })
                    group_cursor_ms += allocated_durations.get(g_s, 0)

                current_offset_ms += total_duration_ms

            elif s_type == "SILENT" or slide_audios[slide_num] is None:
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
                input_wav_paths.append(dest_wav_path)
                notes = slide_notes.get(slide_num, "")

                slide_audio_metadata[str(slide_num)] = {
                    "filename": dest_wav_name,
                    "duration_ms": int(duration_ms),
                    "type": "SILENT",
                    "notes": notes
                }

                events.append({
                    "id": len(events) + 1,
                    "time_ms": int(current_offset_ms),
                    "action": "goto_slide",
                    "slide": slide_num
                })
                current_offset_ms += duration_ms

            else:
                src_audio_path = slide_audios[slide_num]
                dest_wav_name = f"slide_{slide_num}.wav"
                dest_wav_path = slide_audio_pkg_dir / dest_wav_name

                # Canonicalize audio (decode MP3/WAV to 44.1kHz stereo PCM 16-bit)
                duration_ms = self.convert_to_canonical_wav(src_audio_path, dest_wav_path)
                input_wav_paths.append(dest_wav_path)
                notes = slide_notes.get(slide_num, "")

                slide_audio_metadata[str(slide_num)] = {
                    "filename": dest_wav_name,
                    "duration_ms": int(duration_ms),
                    "type": "AUDIO",
                    "notes": notes
                }

                events.append({
                    "id": len(events) + 1,
                    "time_ms": int(current_offset_ms),
                    "action": "goto_slide",
                    "slide": slide_num
                })
                current_offset_ms += duration_ms

        # Sort timeline events deterministically by time_ms then slide
        events.sort(key=lambda ev: (ev["time_ms"], ev["slide"]))
        for idx, ev in enumerate(events):
            ev["id"] = idx + 1

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
