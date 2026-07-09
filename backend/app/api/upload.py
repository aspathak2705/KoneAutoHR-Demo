from fastapi import APIRouter, Depends, File, Form, UploadFile, HTTPException, status
from sqlalchemy.orm import Session as DBSession
from app.db.database import get_db
from app.schemas.upload import UploadResponse
from app.services.upload_service import upload_service
from app.services.session_service import session_service
from app.core.constants import UploadType

router = APIRouter(prefix="/sessions", tags=["Uploads"])

@router.post("/{session_id}/upload", response_model=UploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_session_file(
    session_id: str,
    file: UploadFile = File(...),
    upload_type: UploadType = Form(...),
    db: DBSession = Depends(get_db)
):
    session = session_service.get_session(db, session_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    return await upload_service.upload_file(db, session_id, file, upload_type)
