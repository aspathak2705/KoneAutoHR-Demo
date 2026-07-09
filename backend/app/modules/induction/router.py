import os
from pathlib import Path
from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session as DBSession

from app.db.database import get_db
from app.services.storage_service import storage_service
from app.core.constants import UploadType
from app.core.exceptions import SessionNotFoundException
from app.modules.induction.services.induction_service import induction_service

router = APIRouter(prefix="/induction", tags=["Induction Preparation"])

@router.post("/{session_id}/prepare", status_code=status.HTTP_202_ACCEPTED)
def prepare_induction(
    session_id: str,
    background_tasks: BackgroundTasks,
    db: DBSession = Depends(get_db)
):
    return induction_service.prepare_induction(db, session_id, background_tasks)

@router.get("/{session_id}/status")
def get_preparation_status(
    session_id: str,
    db: DBSession = Depends(get_db)
):
    return induction_service.get_job_status(db, session_id)

@router.get("/{session_id}/package")
def get_induction_package(
    session_id: str,
    db: DBSession = Depends(get_db)
):
    try:
        session_dir = Path(storage_service.get_session_upload_dir(session_id, UploadType.PRESENTATION)).parent
    except SessionNotFoundException:
        raise HTTPException(status_code=404, detail="Session not found")

    package_path = session_dir / "induction_package.json"
    if not package_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="AI Induction Package has not been prepared yet. Trigger /prepare first."
        )
    return FileResponse(package_path, media_type="application/json", filename="induction_package.json")
