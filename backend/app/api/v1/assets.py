from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session as DBSession
from typing import List, Dict, Any, Optional
from pydantic import BaseModel

from app.db.database import get_db
from app.services.asset_service import asset_service

router = APIRouter(prefix="/assets", tags=["Asset Library"])

class LinkAssetRequest(BaseModel):
    presentation_id: Optional[str] = None
    employee_list_id: Optional[str] = None

@router.get("/presentations")
def list_presentation_assets(db: DBSession = Depends(get_db)):
    """
    Phase G — Returns all reusable presentation assets in Asset Library.
    """
    return asset_service.list_presentation_assets(db)

@router.get("/employee-lists")
def list_employee_list_assets(db: DBSession = Depends(get_db)):
    """
    Phase G — Returns all reusable employee list assets in Asset Library.
    """
    return asset_service.list_employee_list_assets(db)

@router.post("/session/{session_id}/link")
def link_assets_to_session(session_id: str, payload: LinkAssetRequest, db: DBSession = Depends(get_db)):
    """
    Phase C & D — Links selected presentation/employee list asset to session and reuses AI script/FAQs.
    """
    try:
        session = asset_service.link_assets_to_session(
            db=db,
            session_id=session_id,
            presentation_id=payload.presentation_id,
            employee_list_id=payload.employee_list_id
        )
        readiness = asset_service.validate_linked_assets_readiness(db, session_id)
        return {
            "status": "success",
            "session_id": session.id,
            "presentation_id": session.presentation_id,
            "employee_list_id": session.employee_list_id,
            "readiness": readiness
        }
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

class CheckDuplicateRequest(BaseModel):
    file_hash: str
    asset_type: str  # "presentation" or "employee_list"

@router.post("/check-duplicate")
def check_duplicate_asset(payload: CheckDuplicateRequest, db: DBSession = Depends(get_db)):
    """
    Core Architecture — Checks if an uploaded file content hash already exists.
    """
    from app.storage.asset_matcher import asset_matcher
    if payload.asset_type == "presentation":
        existing = asset_matcher.find_duplicate_presentation(db, payload.file_hash)
    elif payload.asset_type == "employee_list":
        existing = asset_matcher.find_duplicate_employee_list(db, payload.file_hash)
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid asset_type")

    if existing:
        return {
            "exists": True,
            "asset_id": existing.id,
            "name": existing.name,
            "storage_path": existing.storage_path
        }
    return {"exists": False}

@router.get("/presentations/{presentation_id}/status")
def get_presentation_asset_status(presentation_id: str, db: DBSession = Depends(get_db)):
    """
    Core Architecture — Returns detailed asset status, version validity, and reference count.
    """
    from app.modules.presentation.presentation_asset_manager import PresentationAssetManager
    mgr = PresentationAssetManager()
    return mgr.get_asset_status(db, presentation_id)
