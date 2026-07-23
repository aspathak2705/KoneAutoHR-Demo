import os
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session as DBSession
from sqlalchemy import text
from app.db.database import get_db
from app.core.config import settings

router = APIRouter(prefix="/health", tags=["Health"])

@router.get("")
def health_check(db: DBSession = Depends(get_db)):
    # 1. Database Check
    db_status = "disconnected"
    try:
        db.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception:
        db_status = "disconnected"

    # 2. Storage Check
    storage_status = "unavailable"
    upload_dir = settings.UPLOAD_DIR
    try:
        if not os.path.exists(upload_dir):
            os.makedirs(upload_dir, exist_ok=True)
        if os.access(upload_dir, os.W_OK):
            storage_status = "available"
    except Exception:
        storage_status = "unavailable"

    # Determine overall status
    is_healthy = db_status == "connected" and storage_status == "available"
    overall_status = "healthy" if is_healthy else "unhealthy"

    response_data = {
        "status": overall_status,
        "database": db_status,
        "storage": storage_status,
        "version": "1.0.0"
    }

    if not is_healthy:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=response_data
        )

    return response_data
