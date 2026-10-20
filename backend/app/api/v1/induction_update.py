import os
import shutil
import tempfile
from pathlib import Path
from typing import Dict, Any
from fastapi import APIRouter, Depends, Form, UploadFile, File, HTTPException, status
from sqlalchemy.orm import Session as DBSession
from loguru import logger

from app.db.database import get_db
from app.repositories.session_repository import session_repository
from app.services.storage_service import storage_service
from app.modules.induction.update_service import induction_update_service

router = APIRouter(prefix="/induction-update", tags=["Incremental Induction Update"])

def _validate_session_ready(session_id: str, db: DBSession):
    session = session_repository.get(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session_dir = storage_service.get_session_dir(session_id)
    manifest = session_dir / "manifest.json"
    if not manifest.exists():
        raise HTTPException(
            status_code=400,
            detail="Session does not have a prepared runtime package. Please prepare runtime first."
        )
    return session, session_dir


@router.post("/{session_id}/analyze-ppt")
async def analyze_updated_ppt(
    session_id: str,
    file: UploadFile = File(...),
    db: DBSession = Depends(get_db)
):
    """
    Analyzes an uploaded revised PowerPoint against the existing session presentation.
    Returns detected changes (UNCHANGED, MODIFIED, ADDED, REMOVED) for HR preview.
    """
    _validate_session_ready(session_id, db)

    if not file.filename.lower().endswith((".pptx", ".ppt")):
        raise HTTPException(status_code=400, detail="Only PowerPoint presentations (.pptx, .ppt) are accepted")

    with tempfile.NamedTemporaryFile(suffix=".pptx", delete=False) as tmp:
        tmp_path = Path(tmp.name)
        try:
            shutil.copyfileobj(file.file, tmp)
            tmp.flush()

            session_dir = storage_service.get_session_dir(session_id)
            current_ppt = session_dir / "presentation.pptx"
            if not current_ppt.exists():
                pptxs = list(session_dir.glob("*.pptx"))
                if pptxs:
                    current_ppt = pptxs[0]
                else:
                    raise HTTPException(status_code=404, detail="Current presentation not found on server")

            current_sigs = induction_update_service.extract_slide_signatures(current_ppt)
            revised_sigs = induction_update_service.extract_slide_signatures(tmp_path)

            diff = induction_update_service.diff_presentations(current_sigs, revised_sigs)
            return {
                "status": "SUCCESS",
                "session_id": session_id,
                "summary": diff["summary"],
                "changes": diff["changes"]
            }
        except Exception as e:
            logger.error(f"InductionUpdateAPI | PPT analysis failed: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to analyze presentation: {str(e)}")
        finally:
            if tmp_path.exists():
                try:
                    tmp_path.unlink()
                except Exception:
                    pass


@router.post("/{session_id}/apply-ppt")
async def apply_updated_ppt(
    session_id: str,
    file: UploadFile = File(...),
    db: DBSession = Depends(get_db)
):
    """
    Confirms and applies a revised PowerPoint presentation to an existing induction.
    Updates affected slides, preserves unchanged slide audio/assets, regenerates timeline.
    """
    _validate_session_ready(session_id, db)

    if not file.filename.lower().endswith((".pptx", ".ppt")):
        raise HTTPException(status_code=400, detail="Only PowerPoint presentations (.pptx, .ppt) are accepted")

    with tempfile.NamedTemporaryFile(suffix=".pptx", delete=False) as tmp:
        tmp_path = Path(tmp.name)
        try:
            shutil.copyfileobj(file.file, tmp)
            tmp.flush()

            session_dir = storage_service.get_session_dir(session_id)
            current_ppt = session_dir / "presentation.pptx"
            if not current_ppt.exists():
                pptxs = list(session_dir.glob("*.pptx"))
                if pptxs:
                    current_ppt = pptxs[0]

            current_sigs = induction_update_service.extract_slide_signatures(current_ppt)
            revised_sigs = induction_update_service.extract_slide_signatures(tmp_path)
            diff = induction_update_service.diff_presentations(current_sigs, revised_sigs)

            result = induction_update_service.apply_updated_ppt(
                session_id=session_id,
                revised_pptx_path=tmp_path,
                diff_result=diff
            )
            return result
        except Exception as e:
            logger.error(f"InductionUpdateAPI | Apply updated PPT failed: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to apply presentation update: {str(e)}")
        finally:
            if tmp_path.exists():
                try:
                    tmp_path.unlink()
                except Exception:
                    pass


@router.post("/{session_id}/single-slide")
async def update_single_slide(
    session_id: str,
    target_slide_number: int = Form(...),
    file: UploadFile = File(...),
    db: DBSession = Depends(get_db)
):
    """
    Updates a single targeted slide from an uploaded single-slide PowerPoint presentation.
    """
    _validate_session_ready(session_id, db)

    if not file.filename.lower().endswith((".pptx", ".ppt")):
        raise HTTPException(status_code=400, detail="Only PowerPoint presentations (.pptx, .ppt) are accepted")

    with tempfile.NamedTemporaryFile(suffix=".pptx", delete=False) as tmp:
        tmp_path = Path(tmp.name)
        try:
            shutil.copyfileobj(file.file, tmp)
            tmp.flush()

            result = induction_update_service.update_single_slide(
                session_id=session_id,
                target_slide_number=target_slide_number,
                single_slide_pptx_path=tmp_path
            )
            return result
        except Exception as e:
            logger.error(f"InductionUpdateAPI | Single slide update failed: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to update single slide: {str(e)}")
        finally:
            if tmp_path.exists():
                try:
                    tmp_path.unlink()
                except Exception:
                    pass


@router.post("/{session_id}/slide-audio")
async def update_slide_audio(
    session_id: str,
    target_slide_number: int = Form(...),
    file: UploadFile = File(...),
    db: DBSession = Depends(get_db)
):
    """
    Updates narration audio for a specific slide (MP3, WAV, etc.).
    Preserves all other slide audio, recalibrates presentation timeline and narration.wav.
    """
    _validate_session_ready(session_id, db)

    ext = Path(file.filename).suffix.lower()
    if ext not in [".wav", ".mp3", ".ogg", ".flac", ".m4a"]:
        raise HTTPException(status_code=400, detail="Only audio files (.wav, .mp3, etc.) are accepted")

    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
        tmp_path = Path(tmp.name)
        try:
            shutil.copyfileobj(file.file, tmp)
            tmp.flush()

            result = induction_update_service.update_slide_audio(
                session_id=session_id,
                target_slide_number=target_slide_number,
                uploaded_audio_path=tmp_path
            )
            return result
        except Exception as e:
            logger.error(f"InductionUpdateAPI | Slide audio update failed: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to update slide audio: {str(e)}")
        finally:
            if tmp_path.exists():
                try:
                    tmp_path.unlink()
                except Exception:
                    pass
