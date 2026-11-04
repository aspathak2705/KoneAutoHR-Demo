import os
import shutil
import tempfile
from pathlib import Path
from typing import Dict, Any, Optional
from urllib.parse import urlparse
from fastapi import APIRouter, Depends, Form, UploadFile, File, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session as DBSession
from loguru import logger

from app.db.database import get_db
from app.repositories.session_repository import session_repository
from app.repositories.presentation_metadata_repository import presentation_metadata_repository
from app.repositories.meeting_repository import meeting_repository
from app.services.storage_service import storage_service
from app.services.meeting_runtime_service import meeting_runtime_service
from app.services.runtime_service import runtime_service
from app.modules.induction.update_service import induction_update_service
from app.modules.presentation.presentation_asset_manager import presentation_asset_manager
from app.modules.presentation.presentation_runtime_controller import get_active_presentation_controller
from app.models.runtime import Runtime

router = APIRouter(prefix="/induction-update", tags=["Incremental Induction Update"])

BLOCKED_RUNTIME_STATES = ["JOINING", "WAITING", "CONNECTED", "PRESENTING"]

def validate_teams_url(url: str) -> str:
    """
    Authoritative validator for Microsoft Teams meeting URLs.
    Validates HTTPS, trusted domains (teams.microsoft.com, teams.live.com, or dev localhost/127.0.0.1),
    and preserves all query parameters.
    """
    if not url or not url.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Teams Meeting URL cannot be empty."
        )
    
    clean_url = url.strip()
    try:
        parsed = urlparse(clean_url)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Malformed Teams Meeting URL: {str(e)}"
        )
    
    if parsed.scheme.lower() != "https" and parsed.hostname not in ["localhost", "127.0.0.1"]:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Teams Meeting URL must use HTTPS protocol."
        )
    
    hostname = (parsed.hostname or "").lower()
    allowed_domains = ["teams.microsoft.com", "teams.live.com", "localhost", "127.0.0.1"]
    domain_valid = any(hostname == d or hostname.endswith(f".{d}") for d in allowed_domains)
    
    if not domain_valid:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid Teams Meeting domain '{hostname}'. Must be an official Microsoft Teams domain (e.g. teams.microsoft.com)."
        )
    
    return clean_url

def _validate_session_ready(session_id: str, db: DBSession):
    session = session_repository.get(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Active runtime guard: cannot update while induction is actively in meeting or presenting
    db_runtime = db.query(Runtime).filter(Runtime.session_id == session_id).order_by(Runtime.updated_at.desc()).first()
    if db_runtime:
        runtime_state = db_runtime.state
        if runtime_state in BLOCKED_RUNTIME_STATES:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Cannot update induction while meeting/presentation is actively running ({runtime_state}). Stop induction first."
            )

    active_controller = get_active_presentation_controller(session_id)
    if active_controller:
        if active_controller._is_paused or active_controller.presentation_state in ["SLIDESHOW_RUNNING", "PAUSED", "EDITOR_OPEN"]:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot update induction while presentation is currently running or paused. Stop presentation first."
            )

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
    teams_meeting_url: Optional[str] = Form(None),
    db: DBSession = Depends(get_db)
):
    """
    Confirms and applies a revised PowerPoint presentation to an existing induction.
    Updates affected slides, preserves unchanged slide audio/assets, regenerates timeline.
    Optionally updates the Teams meeting link in the same operation.
    """
    _validate_session_ready(session_id, db)

    if not file.filename.lower().endswith((".pptx", ".ppt")):
        raise HTTPException(status_code=400, detail="Only PowerPoint presentations (.pptx, .ppt) are accepted")

    # If teams_meeting_url is provided and non-empty, pre-validate before making changes
    clean_teams_url = None
    if teams_meeting_url and teams_meeting_url.strip():
        clean_teams_url = validate_teams_url(teams_meeting_url)

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

            # Sync slide count to DB presentation metadata if session has associated presentation
            session = session_repository.get(db, session_id)
            if session and session.presentation_id:
                new_slide_count = result.get("slides")
                if new_slide_count:
                    meta = presentation_metadata_repository.get_by_presentation(db, session.presentation_id)
                    if meta:
                        presentation_metadata_repository.update(db, meta, slide_count=new_slide_count)
                # Invalidate cached script/narration assets
                try:
                    presentation_asset_manager.invalidate_asset(session.presentation_id, "script")
                    presentation_asset_manager.invalidate_asset(session.presentation_id, "narration")
                except Exception as inv_err:
                    logger.warning(f"Failed to invalidate asset cache for {session.presentation_id}: {inv_err}")

            # Apply teams meeting url update if requested
            if clean_teams_url:
                meeting_res = _apply_meeting_link_update(session_id, clean_teams_url, db)
                result["teams_meeting_update"] = meeting_res

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
    teams_meeting_url: Optional[str] = Form(None),
    db: DBSession = Depends(get_db)
):
    """
    Updates a single targeted slide from an uploaded single-slide PowerPoint presentation.
    Optionally updates the Teams meeting link in the same operation.
    """
    _validate_session_ready(session_id, db)

    if not file.filename.lower().endswith((".pptx", ".ppt")):
        raise HTTPException(status_code=400, detail="Only PowerPoint presentations (.pptx, .ppt) are accepted")

    clean_teams_url = None
    if teams_meeting_url and teams_meeting_url.strip():
        clean_teams_url = validate_teams_url(teams_meeting_url)

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

            # Invalidate cached script/narration assets
            session = session_repository.get(db, session_id)
            if session and session.presentation_id:
                try:
                    presentation_asset_manager.invalidate_asset(session.presentation_id, "script")
                    presentation_asset_manager.invalidate_asset(session.presentation_id, "narration")
                except Exception as inv_err:
                    logger.warning(f"Failed to invalidate asset cache for {session.presentation_id}: {inv_err}")

            if clean_teams_url:
                meeting_res = _apply_meeting_link_update(session_id, clean_teams_url, db)
                result["teams_meeting_update"] = meeting_res

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
    teams_meeting_url: Optional[str] = Form(None),
    db: DBSession = Depends(get_db)
):
    """
    Updates narration audio for a specific slide (MP3, WAV, etc.).
    Preserves all other slide audio, recalibrates presentation timeline and narration.wav.
    Optionally updates the Teams meeting link in the same operation.
    """
    _validate_session_ready(session_id, db)

    ext = Path(file.filename).suffix.lower()
    if ext not in [".wav", ".mp3", ".ogg", ".flac", ".m4a"]:
        raise HTTPException(status_code=400, detail="Only audio files (.wav, .mp3, etc.) are accepted")

    clean_teams_url = None
    if teams_meeting_url and teams_meeting_url.strip():
        clean_teams_url = validate_teams_url(teams_meeting_url)

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

            # Invalidate cached script/narration assets
            session = session_repository.get(db, session_id)
            if session and session.presentation_id:
                try:
                    presentation_asset_manager.invalidate_asset(session.presentation_id, "script")
                    presentation_asset_manager.invalidate_asset(session.presentation_id, "narration")
                except Exception as inv_err:
                    logger.warning(f"Failed to invalidate asset cache for {session.presentation_id}: {inv_err}")

            if clean_teams_url:
                meeting_res = _apply_meeting_link_update(session_id, clean_teams_url, db)
                result["teams_meeting_update"] = meeting_res

            return result

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


class UpdateTeamsMeetingLinkRequest(BaseModel):
    teams_meeting_url: str


def _apply_meeting_link_update(session_id: str, teams_meeting_url: str, db: DBSession) -> Dict[str, Any]:
    """
    Core business logic for updating the Teams meeting link of an existing induction.
    Updates existing Meeting record, invalidates runtime coordinator cache if prepared,
    and returns update summary.
    """
    clean_url = validate_teams_url(teams_meeting_url)
    
    # Verify session exists
    session = session_repository.get(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    meeting = meeting_repository.get_by_session(db, session_id)
    if not meeting:
        raise HTTPException(
            status_code=400,
            detail="No meeting configuration found for this induction. Create initial meeting schedule first."
        )

    old_url = meeting.teams_meeting_url
    if old_url == clean_url:
        return {
            "status": "SUCCESS",
            "message": "Teams meeting link is identical; no changes required.",
            "session_id": session_id,
            "teams_meeting_url": clean_url,
            "reprepare_required": False
        }

    # Update meeting record in DB
    meeting.teams_meeting_url = clean_url
    meeting.meeting_status = "PENDING"
    db.add(meeting)

    # Invalidate runtime coordinator and reset runtime state to NOT_CREATED if currently prepared/ready
    reprepare_required = False
    runtime_service.remove_coordinator(session_id)
    
    db_runtime = db.query(Runtime).filter(Runtime.session_id == session_id).order_by(Runtime.updated_at.desc()).first()
    if db_runtime and db_runtime.state in ["READY", "PREPARING", "BROWSER_READY"]:
        db_runtime.state = "NOT_CREATED"
        db_runtime.browser_state = "NOT_CREATED"
        db.add(db_runtime)
        reprepare_required = True
        logger.info(f"InductionUpdateAPI | Reset runtime state to NOT_CREATED for session {session_id} due to Teams URL change.")

    db.commit()
    db.refresh(meeting)

    return {
        "status": "SUCCESS",
        "message": "Microsoft Teams meeting link updated successfully." + (" Please re-prepare runtime before starting." if reprepare_required else ""),
        "session_id": session_id,
        "meeting_id": meeting.id,
        "teams_meeting_url": meeting.teams_meeting_url,
        "reprepare_required": reprepare_required
    }


@router.post("/{session_id}/teams-link")
async def update_teams_meeting_link(
    session_id: str,
    payload: UpdateTeamsMeetingLinkRequest,
    db: DBSession = Depends(get_db)
):
    """
    Updates the Microsoft Teams meeting URL for an existing induction session.
    Preserves all presentation, script, audio and participant associations.
    Invalidates runtime coordinator and requires re-preparation if runtime was already prepared.
    """
    _validate_session_ready(session_id, db)
    return _apply_meeting_link_update(session_id, payload.teams_meeting_url, db)
