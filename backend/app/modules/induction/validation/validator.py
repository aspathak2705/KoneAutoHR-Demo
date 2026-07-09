import os
from sqlalchemy.orm import Session as DBSession
from app.models.session import Session
from app.core.exceptions import ValidationException, SessionNotFoundException
from app.core.constants import UploadType

def validate_session_assets(db: DBSession, session_id: str) -> tuple[str, str]:
    """
    Validates that a session exists, contains all required metadata,
    and that both PowerPoint and Employee list files are uploaded.
    Returns:
        tuple[str, str]: (ppt_file_path, excel_file_path)
    """
    # 1. Fetch Session
    session = db.query(Session).filter(Session.id == session_id).first()
    if not session:
        raise SessionNotFoundException(session_id)

    # 2. Check metadata completeness
    if not session.name:
        raise ValidationException("Session name is missing.")

    # 3. Check uploaded files
    ppt_path = None
    excel_path = None

    for upload in session.uploads:
        if upload.upload_type == UploadType.PRESENTATION.value:
            if upload.file_path and os.path.exists(upload.file_path):
                ppt_path = upload.file_path
        elif upload.upload_type == UploadType.EMPLOYEE_LIST.value:
            if upload.file_path and os.path.exists(upload.file_path):
                excel_path = upload.file_path

    if not ppt_path:
        raise ValidationException("PowerPoint presentation file is missing or not uploaded.")
    if not excel_path:
        raise ValidationException("Employee Excel list file is missing or not uploaded.")

    return ppt_path, excel_path
