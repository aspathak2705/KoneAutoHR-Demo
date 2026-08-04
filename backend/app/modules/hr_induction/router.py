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

    metadata[str(slide_number)] = {
        "audio_path": str(target_path.resolve()),
        "duration_ms": int(duration_ms),
        "notes": notes or ""
    }

    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    return {
        "status": "SUCCESS",
        "slide_number": slide_number,
        "duration_ms": int(duration_ms),
        "notes": notes or ""
    }

@router.post("/validate")
def validate_hr_induction(
    session_id: str,
    db: DBSession = Depends(get_db)
):
    """
    Validates that every slide in the presentation has an uploaded narration audio.
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
    for s_num in range(1, slide_count + 1):
        s_key = str(s_num)
        if s_key not in metadata:
            errors.append(f"Slide {s_num} is missing an audio recording")
        else:
            entry = metadata[s_key]
            audio_path = Path(entry["audio_path"])
            if not audio_path.exists():
                errors.append(f"Audio file for slide {s_num} does not exist on disk")
            if entry["duration_ms"] <= 0:
                errors.append(f"Audio for slide {s_num} has an invalid duration (0s)")

    if errors:
        return {
            "valid": False,
            "errors": errors
        }

    return {
        "valid": True,
        "slide_count": slide_count,
        "total_duration_ms": sum(item["duration_ms"] for item in metadata.values())
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
    slide_audios = {int(k): Path(v["audio_path"]) for k, v in metadata.items()}
    slide_notes = {int(k): v["notes"] for k, v in metadata.items()}
    
    session_dir = storage_service.get_session_dir(session_id)
    presentation_name = Path(session.presentation.storage_path).name

    try:
        package_builder.build_hr_package(
            session_id=session_id,
            session_dir=session_dir,
            presentation_filename=presentation_name,
            slide_count=slide_count,
            slide_audios=slide_audios,
            slide_notes=slide_notes
        )
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
