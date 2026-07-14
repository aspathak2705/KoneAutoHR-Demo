from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session as DBSession
from app.db.database import get_db
from app.schemas.presentation_script import PresentationScriptResponse, PresentationScriptUpdate
from app.services.presentation_script_service import presentation_script_service
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/presentation-script", tags=["Saved Presentation Scripts"])

class ScriptRegenerateRequest(BaseModel):
    presentation_id: str
    employee_list_id: str
    company_name: Optional[str] = "KONE"

@router.get("/{presentation_id}", response_model=PresentationScriptResponse)
def get_presentation_script(presentation_id: str, db: DBSession = Depends(get_db)):
    script = presentation_script_service.get_active_script(db, presentation_id)
    if not script:
        raise HTTPException(status_code=404, detail="No active script found for this presentation")
    return script

@router.put("/{id}", response_model=PresentationScriptResponse)
def update_presentation_script(
    id: str,
    payload: PresentationScriptUpdate,
    db: DBSession = Depends(get_db)
):
    try:
        return presentation_script_service.update_script(db, id, payload.script_content)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/regenerate", response_model=PresentationScriptResponse, status_code=status.HTTP_201_CREATED)
async def regenerate_presentation_script(
    payload: ScriptRegenerateRequest,
    db: DBSession = Depends(get_db)
):
    try:
        return await presentation_script_service.generate_script_and_questions(
            db, 
            payload.presentation_id, 
            payload.employee_list_id, 
            payload.company_name
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
