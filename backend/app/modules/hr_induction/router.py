import json
import os
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, Depends, Form, UploadFile, File, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session as DBSession
from loguru import logger

from app.db.database import get_db
from app.repositories.session_repository import session_repository
from app.services.storage_service import storage_service
from app.modules.presentation.package_builder.package_builder import package_builder
from app.core.constants import SessionStatus
from app.core.exceptions import SessionNotFoundException

router = APIRouter(prefix="/hr-induction", tags=["HR Recorded Induction"])

def get_temp_audio_dir(session_id: str) -> Path:
    session_dir = storage_service.get_session_dir(session_id)
    temp_dir = session_dir / "temp_slide_audios"
    temp_dir.mkdir(parents=True, exist_ok=True)
    return temp_dir

def get_metadata_path(session_id: str) -> Path:
    return storage_service.get_session_dir(session_id) / "hr_slide_metadata.json"

@router.get("/slides/{session_id}/{slide_number}.png")
def get_slide_thumbnail(session_id: str, slide_number: int):
    """
    Returns slide image thumbnail if extracted.
    """
    session_dir = storage_service.get_session_dir(session_id)
    slides_dir = session_dir / "presentation_assets" / "slides"
    # Try zero-padded (extractor standard: slide_001.png)
    path = slides_dir / f"slide_{slide_number:03d}.png"
    if not path.exists():
        path = slides_dir / f"slide_{slide_number}.png"
    if not path.exists():
        path = slides_dir / f"slide_{slide_number:03d}.jpg"
    if not path.exists():
        path = slides_dir / f"slide_{slide_number}.jpg"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Slide thumbnail not found")
    return FileResponse(path, media_type="image/png")


@router.get("/metadata/{session_id}")
def get_hr_metadata(session_id: str):
    """
    Returns current slide metadata mapping for session if present.
    """
    metadata_path = get_metadata_path(session_id)
    if not metadata_path.exists():
        return {"metadata": {}}
    try:
        with open(metadata_path, "r", encoding="utf-8") as f:
            metadata = json.load(f)
        return {"metadata": metadata}
    except Exception as e:
        logger.error(f"Failed to read metadata: {e}")
        return {"metadata": {}}


@router.post("/upload-slide-audio")
async def upload_slide_audio(
    session_id: str = Form(...),
    slide_number: int = Form(...),
    notes: Optional[str] = Form(None),
    audio_file: UploadFile = File(...),
    db: DBSession = Depends(get_db)
):
    """
    Uploads recorded audio for a specific slide number.
    Saves it to a temp folder and registers slide notes.
    """
    logger.info(f"HRInduction | Uploading audio for session: {session_id}, slide: {slide_number}")
    session = session_repository.get(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Validate file extension
    ext = Path(audio_file.filename).suffix.lower()
    if ext not in [".wav", ".mp3"]:
         raise HTTPException(status_code=400, detail="Unsupported audio format. Only WAV and MP3 are allowed.")

    # Save audio file to temp directory
    temp_dir = get_temp_audio_dir(session_id)
    target_path = temp_dir / f"slide_{slide_number}{ext}"
    
    try:
        with target_path.open("wb") as buffer:
            while chunk := await audio_file.read(1024 * 1024):
                buffer.write(chunk)
    except Exception as e:
        logger.error(f"HRInduction | Failed to save file: {e}")
        raise HTTPException(status_code=500, detail="Failed to save audio file")

    # Calculate duration
    duration_ms = package_builder.get_wav_duration_ms(target_path)
    if duration_ms <= 0:
        # Fallback approximation for MP3 or WAV parsing fallback
        try:
            size_bytes = target_path.stat().st_size
            duration_ms = max(3000.0, (size_bytes / 16000.0) * 1000.0)
        except Exception:
            duration_ms = 5000.0

    # Load and update metadata JSON file
    metadata_path = get_metadata_path(session_id)
    metadata = {}
    if metadata_path.exists():
        try:
            with open(metadata_path, "r", encoding="utf-8") as f:
                metadata = json.load(f)
        except Exception:
            pass

    # If slide was part of a group, clean up linked entries
    old_entry = metadata.get(str(slide_number), {})
    if old_entry.get("type") == "GROUP_MASTER":
        for g_s in old_entry.get("group_slides", []):
            if g_s != slide_number and str(g_s) in metadata and metadata[str(g_s)].get("type") == "GROUP_LINKED":
                del metadata[str(g_s)]
    elif old_entry.get("type") == "GROUP_LINKED":
        m_s = old_entry.get("master_slide")
        if m_s and str(m_s) in metadata:
            del metadata[str(m_s)]

    metadata[str(slide_number)] = {
        "type": "AUDIO",
        "audio_path": str(target_path.resolve()),
        "duration_ms": int(duration_ms),
        "notes": notes or ""
    }

    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    return {
        "status": "SUCCESS",
        "slide_number": slide_number,
        "type": "AUDIO",
        "duration_ms": int(duration_ms),
        "notes": notes or ""
    }

@router.post("/set-slide-silent")
def set_slide_silent(
    session_id: str = Form(...),
    slide_number: int = Form(...),
    db: DBSession = Depends(get_db)
):
    """
    Explicitly marks a slide as SILENT with a 5-second timeline duration.
    Removes any previously uploaded audio file for this slide.
    """
    logger.info(f"HRInduction | Marking slide {slide_number} as SILENT for session {session_id}")
    session = session_repository.get(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if not session.presentation:
        raise HTTPException(status_code=400, detail="No presentation linked to this session")

    # Validate slide number against slide count
    slide_count = session.presentation.slide_count or 0
    if slide_count == 0 and session.presentation.metadata_records:
        slide_count = session.presentation.metadata_records[0].slide_count or 0

    if slide_count > 0 and (slide_number < 1 or slide_number > slide_count):
        raise HTTPException(status_code=400, detail=f"Slide number {slide_number} is out of bounds (1..{slide_count})")

    # Safely remove any existing temp audio files for this slide
    temp_dir = get_temp_audio_dir(session_id)
    for ext in [".wav", ".mp3"]:
        old_f = temp_dir / f"slide_{slide_number}{ext}"
        if old_f.exists():
            try:
                old_f.unlink()
            except Exception as e:
                logger.warning(f"HRInduction | Failed to delete old audio {old_f}: {e}")

    # Update metadata
    metadata_path = get_metadata_path(session_id)
    metadata = {}
    if metadata_path.exists():
        try:
            with open(metadata_path, "r", encoding="utf-8") as f:
                metadata = json.load(f)
        except Exception:
            pass

    existing_notes = metadata.get(str(slide_number), {}).get("notes", "")

    # If slide was part of a group, clean up linked entries
    old_entry = metadata.get(str(slide_number), {})
    if old_entry.get("type") == "GROUP_MASTER":
        for g_s in old_entry.get("group_slides", []):
            if g_s != slide_number and str(g_s) in metadata and metadata[str(g_s)].get("type") == "GROUP_LINKED":
                del metadata[str(g_s)]
    elif old_entry.get("type") == "GROUP_LINKED":
        m_s = old_entry.get("master_slide")
        if m_s and str(m_s) in metadata:
            del metadata[str(m_s)]

    metadata[str(slide_number)] = {
        "type": "SILENT",
        "audio_path": None,
        "duration_ms": 5000,
        "notes": existing_notes
    }

    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    return {
        "status": "SUCCESS",
        "slide_number": slide_number,
        "type": "SILENT",
        "duration_ms": 5000,
        "notes": existing_notes
    }

@router.post("/set-slide-group")
async def set_slide_group(
    session_id: str = Form(...),
    start_slide: int = Form(...),
    end_slide: int = Form(...),
    audio_file: Optional[UploadFile] = File(None),
    notes: Optional[str] = Form(None),
    db: DBSession = Depends(get_db)
):
    """
    Assigns one continuous audio recording across consecutive slides start_slide..end_slide.
    Slide start_slide becomes GROUP_MASTER and slides (start_slide+1..end_slide) become GROUP_LINKED.
    """
    logger.info(f"HRInduction | Setting slide group {start_slide}-{end_slide} for session {session_id}")
    session = session_repository.get(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if not session.presentation:
        raise HTTPException(status_code=400, detail="No presentation linked to this session")

    # Validate slide counts
    slide_count = session.presentation.slide_count or 0
    if slide_count == 0 and session.presentation.metadata_records:
        slide_count = session.presentation.metadata_records[0].slide_count or 0

    if end_slide <= start_slide:
        raise HTTPException(status_code=400, detail=f"end_slide ({end_slide}) must be strictly greater than start_slide ({start_slide})")

    if start_slide < 1:
        raise HTTPException(status_code=400, detail=f"start_slide ({start_slide}) must be >= 1")

    if slide_count > 0 and end_slide > slide_count:
        raise HTTPException(status_code=400, detail=f"end_slide ({end_slide}) exceeds slide count ({slide_count})")

    temp_dir = get_temp_audio_dir(session_id)
    group_slides = list(range(start_slide, end_slide + 1))
    group_id = f"group_{start_slide}_{end_slide}"

    metadata_path = get_metadata_path(session_id)
    metadata = {}
    if metadata_path.exists():
        try:
            with open(metadata_path, "r", encoding="utf-8") as f:
                metadata = json.load(f)
        except Exception:
            pass

    # If audio_file is provided, save it
    target_path = None
    duration_ms = 0.0
    if audio_file:
        ext = Path(audio_file.filename).suffix.lower()
        if ext not in [".wav", ".mp3"]:
            raise HTTPException(status_code=400, detail="Audio file must be .wav or .mp3")

        dest_name = f"slide_{start_slide}_group{ext}"
        target_path = temp_dir / dest_name
        contents = await audio_file.read()
        with open(target_path, "wb") as f:
            f.write(contents)

        if ext == ".wav":
            duration_ms = package_builder.get_wav_duration_ms(target_path)
            if duration_ms <= 0:
                target_path.unlink(missing_ok=True)
                raise HTTPException(status_code=400, detail="Uploaded WAV file has invalid duration (0s)")
        else:
            duration_ms = 15000.0 * len(group_slides)  # Default fallback for MP3
    else:
        # Check if master slide already had an audio file
        existing_master = metadata.get(str(start_slide), {})
        if existing_master.get("audio_path") and Path(existing_master["audio_path"]).exists():
            target_path = Path(existing_master["audio_path"])
            duration_ms = existing_master.get("duration_ms", 0.0)
        else:
            raise HTTPException(status_code=400, detail="Audio file is required for the slide group")

    # Clean up old audio files for linked slides
    for s_num in range(start_slide + 1, end_slide + 1):
        for ext in [".wav", ".mp3"]:
            old_f = temp_dir / f"slide_{s_num}{ext}"
            if old_f.exists():
                try:
                    old_f.unlink()
                except Exception as e:
                    logger.warning(f"HRInduction | Failed to delete old audio {old_f}: {e}")

    # Set master entry
    metadata[str(start_slide)] = {
        "type": "GROUP_MASTER",
        "group_id": group_id,
        "audio_path": str(target_path.resolve()),
        "duration_ms": int(duration_ms),
        "group_slides": group_slides,
        "notes": notes if notes is not None else metadata.get(str(start_slide), {}).get("notes", "")
    }

    # Set linked entries
    for s_num in range(start_slide + 1, end_slide + 1):
        metadata[str(s_num)] = {
            "type": "GROUP_LINKED",
            "group_id": group_id,
            "master_slide": start_slide,
            "audio_path": None,
            "duration_ms": 0,
            "notes": metadata.get(str(s_num), {}).get("notes", "")
        }

    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    return {
        "status": "SUCCESS",
        "group_id": group_id,
        "start_slide": start_slide,
        "end_slide": end_slide,
        "duration_ms": int(duration_ms),
        "group_slides": group_slides
    }

@router.post("/unset-slide-group")
def unset_slide_group(
    session_id: str = Form(...),
    group_id: str = Form(...),
    db: DBSession = Depends(get_db)
):
    """
    Dissolves a slide group, resetting all affected slides to unassigned status.
    """
    logger.info(f"HRInduction | Unsetting group {group_id} for session {session_id}")
    metadata_path = get_metadata_path(session_id)
    if not metadata_path.exists():
        raise HTTPException(status_code=400, detail="No metadata found")

    with open(metadata_path, "r", encoding="utf-8") as f:
        metadata = json.load(f)

    to_remove = [k for k, v in metadata.items() if v.get("group_id") == group_id]
    if not to_remove:
        raise HTTPException(status_code=404, detail=f"Group {group_id} not found")

    for k in to_remove:
        del metadata[k]

    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    return {"status": "SUCCESS", "unlinked_slides": [int(k) for k in to_remove]}

@router.post("/validate")
def validate_hr_induction(
    session_id: str,
    db: DBSession = Depends(get_db)
):
    """
    Validates that every slide in the presentation has an uploaded narration audio, is SILENT, or is part of a valid GROUP.
    """
    session = session_repository.get(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if not session.presentation:
        raise HTTPException(status_code=400, detail="No presentation linked to this session")

    # Retrieve expected slide count from presentation metadata
    slide_count = 0
    if session.presentation.metadata_records:
        slide_count = session.presentation.metadata_records[0].slide_count

    if slide_count <= 0:
        raise HTTPException(status_code=400, detail="Presentation slide count is zero or not processed yet")

    metadata_path = get_metadata_path(session_id)
    if not metadata_path.exists():
        raise HTTPException(status_code=400, detail="No slide audio uploads found")

    try:
        with open(metadata_path, "r", encoding="utf-8") as f:
            metadata = json.load(f)
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to parse slide metadata")

    errors = []
    total_duration_ms = 0

    for s_num in range(1, slide_count + 1):
        s_key = str(s_num)
        if s_key not in metadata:
            errors.append(f"Slide {s_num} is missing an audio recording, silent selection, or group assignment")
        else:
            entry = metadata[s_key]
            entry_type = entry.get("type", "AUDIO")

            if entry_type == "SILENT":
                if entry.get("duration_ms") != 5000:
                    errors.append(f"Slide {s_num} marked silent has invalid duration ({entry.get('duration_ms')}ms)")
                else:
                    total_duration_ms += 5000
            elif entry_type == "GROUP_MASTER":
                if not entry.get("audio_path"):
                    errors.append(f"Group master slide {s_num} is missing an audio file path")
                else:
                    audio_path = Path(entry["audio_path"])
                    if not audio_path.exists():
                        errors.append(f"Group audio file for slide {s_num} does not exist on disk")
                    if entry.get("duration_ms", 0) <= 0:
                        errors.append(f"Group audio for slide {s_num} has an invalid duration (0s)")
                    else:
                        total_duration_ms += entry.get("duration_ms", 0)

                # Verify linked slides exist and match
                group_slides = entry.get("group_slides", [])
                for g_s in group_slides:
                    if g_s != s_num:
                        linked_entry = metadata.get(str(g_s))
                        if not linked_entry or linked_entry.get("type") != "GROUP_LINKED" or linked_entry.get("master_slide") != s_num:
                            errors.append(f"Slide {g_s} is not properly linked to master slide {s_num}")
            elif entry_type == "GROUP_LINKED":
                master_num = entry.get("master_slide")
                if not master_num or str(master_num) not in metadata:
                    errors.append(f"Linked slide {s_num} points to non-existent master slide {master_num}")
                else:
                    master_entry = metadata[str(master_num)]
                    if master_entry.get("type") != "GROUP_MASTER" or s_num not in master_entry.get("group_slides", []):
                        errors.append(f"Linked slide {s_num} not declared in master slide {master_num} group")
            else:
                if not entry.get("audio_path"):
                    errors.append(f"Slide {s_num} is missing an audio file path")
                else:
                    audio_path = Path(entry["audio_path"])
                    if not audio_path.exists():
                        errors.append(f"Audio file for slide {s_num} does not exist on disk")
                    if entry.get("duration_ms", 0) <= 0:
                        errors.append(f"Audio for slide {s_num} has an invalid duration (0s)")
                    else:
                        total_duration_ms += entry.get("duration_ms", 0)

    if errors:
        return {
            "valid": False,
            "errors": errors
        }

    return {
        "valid": True,
        "slide_count": slide_count,
        "total_duration_ms": total_duration_ms
    }

@router.post("/build-package")
def build_package(
    session_id: str,
    db: DBSession = Depends(get_db)
):
    """
    Combines slide audio and creates the standard presentation package, moving the session status to PREPARED.
    """
    session = session_repository.get(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Run validation
    validation = validate_hr_induction(session_id, db)
    if not validation.get("valid"):
        raise HTTPException(
            status_code=400,
            detail={"message": "Induction validation failed", "errors": validation.get("errors")}
        )

    slide_count = validation["slide_count"]
    metadata_path = get_metadata_path(session_id)
    with open(metadata_path, "r", encoding="utf-8") as f:
        metadata = json.load(f)

    # Prepare PackageBuilder dicts
    slide_audios = {
        int(k): Path(v["audio_path"]) if v.get("audio_path") else None 
        for k, v in metadata.items()
    }
    slide_notes = {int(k): v.get("notes", "") for k, v in metadata.items()}
    slide_types = {int(k): v.get("type", "AUDIO") for k, v in metadata.items()}
    slide_groups = {
        int(k): {
            "group_id": v.get("group_id"),
            "master_slide": v.get("master_slide"),
            "group_slides": v.get("group_slides"),
            "duration_ms": v.get("duration_ms", 0),
            "slide_durations_ms": v.get("slide_durations_ms", {})
        }
        for k, v in metadata.items()
        if v.get("type") in ("GROUP_MASTER", "GROUP_LINKED")
    }
    
    session_dir = storage_service.get_session_dir(session_id)
    presentation_name = Path(session.presentation.storage_path).name

    from app.modules.presentation.presentation_asset_manager import presentation_asset_manager
    assets_status = presentation_asset_manager.check_assets(db, session.presentation_id, "HR")
    paths = presentation_asset_manager.get_asset_paths(session.presentation_id, "HR")

    if assets_status["narration_exists"] and assets_status["timeline_exists"] and assets_status["manifest_exists"]:
        logger.info(f"HRInduction | Reusable assets found for presentation {session.presentation_id}. Copying cached artifacts...")
        import shutil
        shutil.copy2(paths["narration"], session_dir / "narration.wav")
        shutil.copy2(paths["timeline"], session_dir / "presentation_timeline.json")
        shutil.copy2(paths["manifest"], session_dir / "manifest.json")
        
        # Also copy slide images if they exist
        if paths["slides_dir"].exists():
            session_slides_dir = session_dir / "presentation_assets" / "slides"
            session_slides_dir.mkdir(parents=True, exist_ok=True)
            for slide_img in paths["slides_dir"].glob("slide_*.png"):
                shutil.copy2(slide_img, session_slides_dir / slide_img.name)
    else:
        try:
            package_builder.build_hr_package(
                session_id=session_id,
                session_dir=session_dir,
                presentation_filename=presentation_name,
                slide_count=slide_count,
                slide_audios=slide_audios,
                slide_notes=slide_notes,
                slide_types=slide_types,
                slide_groups=slide_groups
            )
            # Copy generated outputs to presentation asset manager cache
            import shutil
            shutil.copy2(session_dir / "narration.wav", paths["narration"])
            shutil.copy2(session_dir / "presentation_timeline.json", paths["timeline"])
            shutil.copy2(session_dir / "manifest.json", paths["manifest"])
            
            # Copy slide images to presentation asset manager cache if they exist
            session_slides_dir = session_dir / "presentation_assets" / "slides"
            if session_slides_dir.exists():
                paths["slides_dir"].mkdir(parents=True, exist_ok=True)
                for slide_img in session_slides_dir.glob("slide_*.png"):
                    shutil.copy2(slide_img, paths["slides_dir"] / slide_img.name)
                    
        except Exception as e:
            logger.exception(f"HRInduction | Failed to build package: {e}")
            raise HTTPException(status_code=500, detail=f"Package build failed: {str(e)}")

    # Update session status
    try:
        session.status = "PREPARED"
        session.creation_mode = "HR"
        session.package_version = "1.0.0"
        session.package_path = str(session_dir)
        db.add(session)
        db.commit()
    except Exception as db_err:
        logger.error(f"HRInduction | Database update failed: {db_err}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Database update failed")

    return {
        "status": "SUCCESS",
        "message": "Presentation package compiled and session marked as PREPARED"
    }
