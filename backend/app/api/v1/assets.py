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
