from fastapi import Depends
from sqlalchemy.orm import Session as DBSession
from app.db.database import get_db as _get_db_original
from app.core.config import settings, Settings
from app.db.unit_of_work import UnitOfWork

# Import services
from app.services.session_service import session_service, SessionService
from app.services.upload_service import upload_service, UploadService
from app.services.presentation_service import presentation_service, PresentationService

def get_settings() -> Settings:
    return settings

def get_db():
    yield from _get_db_original()

def get_uow(db: DBSession = Depends(get_db)):
    return UnitOfWork(db)

def get_session_service() -> SessionService:
    return session_service

def get_upload_service() -> UploadService:
    return upload_service

def get_presentation_service() -> PresentationService:
    return presentation_service
