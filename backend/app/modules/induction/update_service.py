import os
import json
import shutil
import difflib
import wave
import traceback
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from loguru import logger

from app.services.storage_service import storage_service
from app.modules.presentation.package_builder.package_builder import (
    package_builder,
    CANONICAL_RATE,
    CANONICAL_CHANNELS,
    CANONICAL_SAMPWIDTH
)

class InductionUpdateService:
    """
    Handles granular, incremental updates to existing prepared inductions:
    1. Single slide update (replaces 1 slide via PowerPoint automation, regens thumbnail, flags narration)
    2. Slide audio update (replaces audio for 1 slide, recalibrates timeline, splices narration.wav)
    3. Full PPT comparison and selective update (diffs slides, preserves unchanged audio/assets, atomic rollback)
    """

    def _get_session_paths(self, session_id: str) -> Dict[str, Path]:
        session_dir = storage_service.get_session_dir(session_id)
        if not session_dir.exists():
            raise FileNotFoundError(f"Session directory not found: {session_dir}")

        presentation_path = session_dir / "presentation.pptx"
        if not presentation_path.exists():
            # Check for alternative pptx names
            pptx_files = list(session_dir.glob("*.pptx"))
            if pptx_files:
                presentation_path = pptx_files[0]

        return {
            "session_dir": session_dir,
            "presentation": presentation_path,
            "manifest": session_dir / "manifest.json",
            "timeline": session_dir / "presentation_timeline.json",
            "narration": session_dir / "narration.wav",
            "metadata": session_dir / "hr_slide_metadata.json",
            "slides_dir": session_dir / "presentation_assets" / "slides",
            "slide_audio_dir": session_dir / "slide_audio",
            "backup_dir": session_dir / ".backup_induction_update"
        }

    def _create_backup(self, paths: Dict[str, Path]) -> None:
        """
        Creates an atomic rollback backup of the current runtime package.
        """
        backup_dir = paths["backup_dir"]
        if backup_dir.exists():
            shutil.rmtree(backup_dir, ignore_errors=True)
        backup_dir.mkdir(parents=True, exist_ok=True)

        for key in ["manifest", "timeline", "metadata"]:
            p = paths[key]
            if p.exists():
                shutil.copy2(p, backup_dir / p.name)

        if paths["presentation"].exists():
            shutil.copy2(paths["presentation"], backup_dir / "presentation.pptx")

        if paths["narration"].exists():
            shutil.copy2(paths["narration"], backup_dir / "narration.wav")

        logger.info(f"InductionUpdateService | Backup created at {backup_dir}")

    def _restore_backup(self, paths: Dict[str, Path]) -> None:
        """
        Restores working state from backup upon error.
        """
        backup_dir = paths["backup_dir"]
        session_dir = paths["session_dir"]
        if not backup_dir.exists():
            logger.warning("InductionUpdateService | No backup found to restore.")
            return

        for p in backup_dir.glob("*"):
            if p.is_file():
                shutil.copy2(p, session_dir / p.name)
        logger.info(f"InductionUpdateService | Successfully restored backup from {backup_dir}")

    def _cleanup_backup(self, paths: Dict[str, Path]) -> None:
        backup_dir = paths["backup_dir"]
        if backup_dir.exists():
            shutil.rmtree(backup_dir, ignore_errors=True)

    def extract_slide_signatures(self, pptx_path: Path) -> List[Dict[str, Any]]:
        """
        Uses win32com PowerPoint automation to inspect slides, titles, and text frames.
        """
        import win32com.client
        import pythoncom
        pythoncom.CoInitialize()

        ppt = None
        pres = None
        signatures = []
        try:
            ppt = win32com.client.Dispatch("PowerPoint.Application")
            pres = ppt.Presentations.Open(str(pptx_path.resolve()), ReadOnly=True, WithWindow=False)
            count = pres.Slides.Count

            for i in range(1, count + 1):
                slide = pres.Slides(i)
                title = ""
                body_texts = []
                for shp in slide.Shapes:
                    if shp.HasTextFrame and shp.TextFrame.HasText:
                        txt = shp.TextFrame.TextRange.Text.strip()
                        if txt:
                            if not title and len(txt) < 80:
                                title = txt
                            else:
                                body_texts.append(txt)

                if not title and body_texts:
                    title = body_texts[0][:60]

                full_text = f"{title}\n" + "\n".join(body_texts)
                signatures.append({
                    "slide_index": i,
                    "title": title or f"Slide {i}",
                    "text": full_text.strip(),
                    "char_count": len(full_text.strip())
                })
        finally:
            if pres:
                try:
                    pres.Close()
                except Exception:
                    pass
            if ppt:
                try:
                    ppt.Quit()
                except Exception:
                    pass
            pythoncom.CoUninitialize()

        return signatures

    def diff_presentations(self, current_sigs: List[Dict[str, Any]], revised_sigs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Compares slide signatures between existing induction and revised presentation.
        Detects UNCHANGED, MODIFIED, ADDED, REMOVED slides.
        """
        current_texts = [s["text"] for s in current_sigs]
        revised_texts = [s["text"] for s in revised_sigs]

        matcher = difflib.SequenceMatcher(None, current_texts, revised_texts)
        changes = []
        matched_current = set()

        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "equal":
                for idx_old, idx_new in zip(range(i1, i2), range(j1, j2)):
                    changes.append({
                        "slide_index": idx_new + 1,
                        "old_slide_index": idx_old + 1,
                        "status": "UNCHANGED",
                        "title": revised_sigs[idx_new]["title"],
                        "details": "Content matches existing slide"
                    })
                    matched_current.add(idx_old + 1)
            elif tag == "replace":
                len_old = i2 - i1
                len_new = j2 - j1
                min_len = min(len_old, len_new)
                for k in range(min_len):
                    idx_old = i1 + k
                    idx_new = j1 + k
                    changes.append({
                        "slide_index": idx_new + 1,
                        "old_slide_index": idx_old + 1,
                        "status": "MODIFIED",
                        "title": revised_sigs[idx_new]["title"],
                        "details": f"Content modified from slide {idx_old + 1}"
                    })
                    matched_current.add(idx_old + 1)
                if len_new > len_old:
                    for idx_new in range(j1 + min_len, j2):
                        changes.append({
                            "slide_index": idx_new + 1,
                            "old_slide_index": None,
                            "status": "ADDED",
                            "title": revised_sigs[idx_new]["title"],
                            "details": "New slide inserted"
                        })
                elif len_old > len_new:
                    for idx_old in range(i1 + min_len, i2):
                        changes.append({
                            "slide_index": None,
                            "old_slide_index": idx_old + 1,
                            "status": "REMOVED",
                            "title": current_sigs[idx_old]["title"],
                            "details": f"Slide {idx_old + 1} was removed"
                        })
                        matched_current.add(idx_old + 1)
            elif tag == "insert":
                for idx_new in range(j1, j2):
                    changes.append({
                        "slide_index": idx_new + 1,
                        "old_slide_index": None,
                        "status": "ADDED",
                        "title": revised_sigs[idx_new]["title"],
                        "details": "New slide inserted"
                    })
            elif tag == "delete":
                for idx_old in range(i1, i2):
                    changes.append({
                        "slide_index": None,
                        "old_slide_index": idx_old + 1,
                        "status": "REMOVED",
                        "title": current_sigs[idx_old]["title"],
                        "details": f"Slide {idx_old + 1} was removed"
                    })
                    matched_current.add(idx_old + 1)

        summary = {
            "unchanged": sum(1 for c in changes if c["status"] == "UNCHANGED"),
            "modified": sum(1 for c in changes if c["status"] == "MODIFIED"),
            "added": sum(1 for c in changes if c["status"] == "ADDED"),
            "removed": sum(1 for c in changes if c["status"] == "REMOVED"),
            "total_new_slides": len(revised_sigs)
        }

        return {
            "summary": summary,
            "changes": changes
        }

    def update_single_slide(
        self,
        session_id: str,
        target_slide_number: int,
        single_slide_pptx_path: Path
    ) -> Dict[str, Any]:
        """
        Replaces target_slide_number in session presentation with slide 1 of single_slide_pptx_path.
        Re-exports thumbnail for only this slide, flags narration for review in metadata.
        """
        paths = self._get_session_paths(session_id)
        self._create_backup(paths)

        import win32com.client
        import pythoncom
        pythoncom.CoInitialize()

        ppt = None
        pres_src = None
        pres_single = None
        pres_out = None
        temp_out = paths["session_dir"] / "temp_deck_update.pptx"

        try:
            ppt = win32com.client.Dispatch("PowerPoint.Application")
            pres_src = ppt.Presentations.Open(str(paths["presentation"].resolve()), ReadOnly=True, WithWindow=False)
            total_slides = pres_src.Slides.Count

            if target_slide_number < 1 or target_slide_number > total_slides:
                raise ValueError(f"Target slide number {target_slide_number} out of bounds (1-{total_slides})")

            pres_single = ppt.Presentations.Open(str(single_slide_pptx_path.resolve()), ReadOnly=True, WithWindow=False)
            if pres_single.Slides.Count < 1:
                raise ValueError("Uploaded slide presentation contains no slides")

            pres_out = ppt.Presentations.Add(True)

            for i in range(1, total_slides + 1):
                if i == target_slide_number:
                    pres_single.Slides(1).Copy()
                    pres_out.Slides.Paste()
                else:
                    pres_src.Slides(i).Copy()
                    pres_out.Slides.Paste()

            pres_out.SaveAs(str(temp_out.resolve()))

            # Export updated slide thumbnail
            paths["slides_dir"].mkdir(parents=True, exist_ok=True)
            thumb_path = paths["slides_dir"] / f"slide_{target_slide_number:03d}.png"
            thumb_path_alt = paths["slides_dir"] / f"slide_{target_slide_number}.png"
            pres_out.Slides(target_slide_number).Export(str(thumb_path.resolve()), "PNG", 1920, 1080)
            if thumb_path_alt.exists():
                shutil.copy2(thumb_path, thumb_path_alt)

            pres_out.Close()
            pres_out = None
            pres_single.Close()
            pres_single = None
            pres_src.Close()
            pres_src = None

            # Overwrite session presentation.pptx
            shutil.move(str(temp_out), str(paths["presentation"]))

            # Flag narration for review in hr_slide_metadata.json
            if paths["metadata"].exists():
                with open(paths["metadata"], "r", encoding="utf-8") as f:
                    meta = json.load(f)
                slide_key = str(target_slide_number)
                if slide_key in meta:
                    meta[slide_key]["needs_review"] = True
                    meta[slide_key]["content_updated"] = True
                with open(paths["metadata"], "w", encoding="utf-8") as f:
                    json.dump(meta, f, indent=2)

            self._cleanup_backup(paths)
            return {
                "status": "SUCCESS",
                "message": f"Slide {target_slide_number} replaced successfully. Narration flagged for review.",
                "slide_number": target_slide_number,
                "thumbnail_updated": True
            }

        except Exception as e:
            logger.error(f"InductionUpdateService | Single slide update failed: {e}\n{traceback.format_exc()}")
            self._restore_backup(paths)
            raise e
        finally:
            for p in [pres_out, pres_single, pres_src]:
                if p:
                    try:
                        p.Close()
                    except Exception:
                        pass
            if ppt:
                try:
                    ppt.Quit()
                except Exception:
                    pass
            pythoncom.CoUninitialize()
            if temp_out.exists():
                try:
                    temp_out.unlink()
                except Exception:
                    pass

    def update_slide_audio(
        self,
        session_id: str,
        target_slide_number: int,
        uploaded_audio_path: Path
    ) -> Dict[str, Any]:
        """
        Replaces audio for target_slide_number with uploaded audio.
        Canonicalizes new audio to 44.1kHz stereo WAV, re-splices narration.wav,
        and recalculates timeline offsets while preserving all other slide audio.
        """
        paths = self._get_session_paths(session_id)
        self._create_backup(paths)

        try:
            if not paths["manifest"].exists():
                raise FileNotFoundError("Manifest file not found for session")

            with open(paths["manifest"], "r", encoding="utf-8") as f:
                manifest = json.load(f)

            slide_audio_meta = manifest.get("slide_audio_metadata", {})
            slide_key = str(target_slide_number)
            if slide_key not in slide_audio_meta:
                raise ValueError(f"Slide {target_slide_number} not found in manifest")

            # Canonicalize uploaded audio into slide_audio dir
            paths["slide_audio_dir"].mkdir(parents=True, exist_ok=True)
            target_wav_name = f"slide_{target_slide_number}.wav"
            target_wav_path = paths["slide_audio_dir"] / target_wav_name

            duration_ms = package_builder.convert_to_canonical_wav(
                src_path=uploaded_audio_path,
                dst_wav_path=target_wav_path
            )

            # Update manifest audio metadata for this slide
            slide_audio_meta[slide_key]["filename"] = target_wav_name
            slide_audio_meta[slide_key]["duration_ms"] = int(duration_ms)
            slide_audio_meta[slide_key]["type"] = "AUDIO"

            # Rebuild presentation_timeline.json and narration.wav
            total_slides = manifest.get("slides", len(slide_audio_meta))
            events = []
            current_offset_ms = 0.0
            wav_paths_to_concat = []

            for s_idx in range(1, total_slides + 1):
                s_k = str(s_idx)
                s_info = slide_audio_meta.get(s_k, {})
                s_filename = s_info.get("filename")
                s_type = s_info.get("type", "AUDIO")

                if s_type == "SILENT" or not s_filename:
                    # Silence wav
                    silent_name = f"slide_{s_idx}_silent.wav"
                    silent_path = paths["slide_audio_dir"] / silent_name
                    if not silent_path.exists():
                        package_builder.generate_silence_wav(silent_path, 5000)
                    wav_paths_to_concat.append(silent_path)
                    s_dur = 5000.0
                else:
                    wav_file = paths["slide_audio_dir"] / s_filename
                    if not wav_file.exists():
                        # fallback silence
                        silent_name = f"slide_{s_idx}_silent.wav"
                        silent_path = paths["slide_audio_dir"] / silent_name
                        if not silent_path.exists():
                            package_builder.generate_silence_wav(silent_path, 5000)
                        wav_paths_to_concat.append(silent_path)
                        s_dur = 5000.0
                    else:
                        wav_paths_to_concat.append(wav_file)
                        s_dur = float(s_info.get("duration_ms", 5000))

                events.append({
                    "id": len(events) + 1,
                    "time_ms": int(current_offset_ms),
                    "action": "goto_slide",
                    "slide": s_idx
                })
                current_offset_ms += s_dur

            # Concatenate WAVs into narration.wav
            self._concatenate_wavs(wav_paths_to_concat, paths["narration"])

            # Save updated timeline
            timeline_data = {
                "version": "1.0",
                "duration_ms": int(current_offset_ms),
                "events": events
            }
            with open(paths["timeline"], "w", encoding="utf-8") as f:
                json.dump(timeline_data, f, indent=2)

            # Save updated manifest
            manifest["duration_ms"] = int(current_offset_ms)
            manifest["slide_audio_metadata"] = slide_audio_meta
            with open(paths["manifest"], "w", encoding="utf-8") as f:
                json.dump(manifest, f, indent=2)

            # Update hr_slide_metadata.json if present
            if paths["metadata"].exists():
                try:
                    with open(paths["metadata"], "r", encoding="utf-8") as f:
                        meta = json.load(f)
                    if slide_key in meta:
                        meta[slide_key]["duration_ms"] = int(duration_ms)
                        meta[slide_key]["type"] = "AUDIO"
                        meta[slide_key]["needs_review"] = False
                    with open(paths["metadata"], "w", encoding="utf-8") as f:
                        json.dump(meta, f, indent=2)
                except Exception as me:
                    logger.warning(f"InductionUpdateService | Could not update hr_slide_metadata: {me}")

            self._cleanup_backup(paths)
            return {
                "status": "SUCCESS",
                "message": f"Audio for slide {target_slide_number} updated successfully.",
                "slide_number": target_slide_number,
                "duration_ms": int(duration_ms),
                "total_duration_ms": int(current_offset_ms)
            }

        except Exception as e:
            logger.error(f"InductionUpdateService | Slide audio update failed: {e}\n{traceback.format_exc()}")
            self._restore_backup(paths)
            raise e

    def apply_updated_ppt(
        self,
        session_id: str,
        revised_pptx_path: Path,
        diff_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Applies a revised full PowerPoint to an existing induction:
        - Replaces presentation.pptx
        - Re-exports slide images for changed/added slides only
        - Maps and preserves existing slide audio for UNCHANGED slides
        - Generates 5s silence for newly added / modified slides (flags for audio review)
        - Rebuilds narration.wav, presentation_timeline.json, and manifest.json
        """
        paths = self._get_session_paths(session_id)
        self._create_backup(paths)

        import win32com.client
        import pythoncom
        pythoncom.CoInitialize()

        ppt = None
        pres_new = None

        try:
            # Load old manifest
            with open(paths["manifest"], "r", encoding="utf-8") as f:
                old_manifest = json.load(f)
            old_audio_meta = old_manifest.get("slide_audio_metadata", {})

            # Open revised PPT to get slide count and export changed thumbnails
            ppt = win32com.client.Dispatch("PowerPoint.Application")
            pres_new = ppt.Presentations.Open(str(revised_pptx_path.resolve()), ReadOnly=True, WithWindow=False)
            new_slide_count = pres_new.Slides.Count

            paths["slides_dir"].mkdir(parents=True, exist_ok=True)
            paths["slide_audio_dir"].mkdir(parents=True, exist_ok=True)

            changes = diff_result.get("changes", [])
            new_audio_meta = {}
            events = []
            current_offset_ms = 0.0
            wav_paths_to_concat = []

            # Process each new slide 1..new_slide_count
            for new_idx in range(1, new_slide_count + 1):
                # Find matching change entry
                change = next((c for c in changes if c.get("slide_index") == new_idx), None)
                status = change.get("status") if change else "MODIFIED"
                old_idx = change.get("old_slide_index") if change else None

                thumb_path = paths["slides_dir"] / f"slide_{new_idx:03d}.png"
                thumb_path_alt = paths["slides_dir"] / f"slide_{new_idx}.png"

                if status == "UNCHANGED" and old_idx:
                    # Reuse old thumbnail if exists, else export
                    old_thumb = paths["slides_dir"] / f"slide_{old_idx:03d}.png"
                    if not old_thumb.exists():
                        pres_new.Slides(new_idx).Export(str(thumb_path.resolve()), "PNG", 1920, 1080)
                    elif old_thumb != thumb_path:
                        shutil.copy2(old_thumb, thumb_path)

                    # Reuse old audio
                    old_meta = old_audio_meta.get(str(old_idx), {})
                    old_wav_name = old_meta.get("filename")
                    old_wav_path = paths["slide_audio_dir"] / old_wav_name if old_wav_name else None

                    if old_wav_path and old_wav_path.exists():
                        new_wav_name = f"slide_{new_idx}.wav" if old_meta.get("type") == "AUDIO" else f"slide_{new_idx}_silent.wav"
                        new_wav_path = paths["slide_audio_dir"] / new_wav_name
                        if old_wav_path != new_wav_path:
                            shutil.copy2(old_wav_path, new_wav_path)
                        wav_paths_to_concat.append(new_wav_path)
                        dur_ms = float(old_meta.get("duration_ms", 5000))
                        new_audio_meta[str(new_idx)] = {
                            "filename": new_wav_name,
                            "duration_ms": int(dur_ms),
                            "type": old_meta.get("type", "AUDIO"),
                            "notes": old_meta.get("notes", "")
                        }
                    else:
                        # Fallback silence
                        sil_name = f"slide_{new_idx}_silent.wav"
                        sil_path = paths["slide_audio_dir"] / sil_name
                        package_builder.generate_silence_wav(sil_path, 5000)
                        wav_paths_to_concat.append(sil_path)
                        dur_ms = 5000.0
                        new_audio_meta[str(new_idx)] = {
                            "filename": sil_name,
                            "duration_ms": 5000,
                            "type": "SILENT",
                            "notes": ""
                        }
                else:
                    # MODIFIED or ADDED slide: Re-export thumbnail, generate silence placeholder
                    pres_new.Slides(new_idx).Export(str(thumb_path.resolve()), "PNG", 1920, 1080)
                    sil_name = f"slide_{new_idx}_silent.wav"
                    sil_path = paths["slide_audio_dir"] / sil_name
                    package_builder.generate_silence_wav(sil_path, 5000)
                    wav_paths_to_concat.append(sil_path)
                    dur_ms = 5000.0
                    new_audio_meta[str(new_idx)] = {
                        "filename": sil_name,
                        "duration_ms": 5000,
                        "type": "SILENT",
                        "notes": "Content updated - audio required"
                    }

                if thumb_path.exists() and thumb_path != thumb_path_alt:
                    try:
                        shutil.copy2(thumb_path, thumb_path_alt)
                    except Exception:
                        pass

                events.append({
                    "id": len(events) + 1,
                    "time_ms": int(current_offset_ms),
                    "action": "goto_slide",
                    "slide": new_idx
                })
                current_offset_ms += dur_ms

            pres_new.Close()
            pres_new = None

            # Copy revised PPT into session presentation.pptx
            shutil.copy2(revised_pptx_path, paths["presentation"])

            # Concatenate WAVs into narration.wav
            self._concatenate_wavs(wav_paths_to_concat, paths["narration"])

            # Save updated timeline
            timeline_data = {
                "version": "1.0",
                "duration_ms": int(current_offset_ms),
                "events": events
            }
            with open(paths["timeline"], "w", encoding="utf-8") as f:
                json.dump(timeline_data, f, indent=2)

            # Save updated manifest
            old_manifest["slides"] = new_slide_count
            old_manifest["duration_ms"] = int(current_offset_ms)
            old_manifest["slide_audio_metadata"] = new_audio_meta
            with open(paths["manifest"], "w", encoding="utf-8") as f:
                json.dump(old_manifest, f, indent=2)

            # Update hr_slide_metadata.json
            with open(paths["metadata"], "w", encoding="utf-8") as f:
                json.dump(new_audio_meta, f, indent=2)

            self._cleanup_backup(paths)
            return {
                "status": "SUCCESS",
                "message": f"Updated presentation applied: {new_slide_count} slides.",
                "slides": new_slide_count,
                "duration_ms": int(current_offset_ms),
                "summary": diff_result.get("summary")
            }

        except Exception as e:
            logger.error(f"InductionUpdateService | Full PPT update failed: {e}\n{traceback.format_exc()}")
            self._restore_backup(paths)
            raise e
        finally:
            if pres_new:
                try:
                    pres_new.Close()
                except Exception:
                    pass
            if ppt:
                try:
                    ppt.Quit()
                except Exception:
                    pass
            pythoncom.CoUninitialize()

    def _concatenate_wavs(self, input_wav_paths: List[Path], output_wav_path: Path) -> None:
        """
        Concatenates canonical 16-bit 44.1kHz stereo WAV files into a single output WAV.
        """
        output_wav_path.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(output_wav_path), "wb") as out_wav:
            out_wav.setnchannels(CANONICAL_CHANNELS)
            out_wav.setsampwidth(CANONICAL_SAMPWIDTH)
            out_wav.setframerate(CANONICAL_RATE)

            for p in input_wav_paths:
                with wave.open(str(p), "rb") as in_wav:
                    # Stream frames in chunks to prevent memory spikes
                    chunk_size = 65536
                    while True:
                        frames = in_wav.readframes(chunk_size)
                        if not frames:
                            break
                        out_wav.writeframes(frames)


induction_update_service = InductionUpdateService()
