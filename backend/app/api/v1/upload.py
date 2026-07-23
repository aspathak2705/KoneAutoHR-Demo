from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from app.core.dependencies import get_session_service, get_upload_service, get_uow
from app.db.unit_of_work import UnitOfWork
from app.schemas.upload import UploadResponse
from app.services.upload_service import UploadService
from app.services.session_service import SessionService
from app.core.constants import UploadType

router = APIRouter(prefix="/sessions", tags=["Uploads"])

@router.post("/{session_id}/upload", response_model=UploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_session_file(
    session_id: str,
    file: UploadFile = File(...),
    upload_type: UploadType = Form(...),
    uow: UnitOfWork = Depends(get_uow),
    session_svc: SessionService = Depends(get_session_service),
    upload_svc: UploadService = Depends(get_upload_service),
):
    session_svc.get_session(uow.db, session_id)
    return await upload_svc.upload_file(uow.db, session_id, file, upload_type)