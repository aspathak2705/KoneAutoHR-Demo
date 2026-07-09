from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session as DBSession
from typing import List
from app.db.database import get_db
from app.schemas.session import SessionCreate, SessionUpdate, SessionResponse, SessionDetailResponse
from app.services.session_service import session_service

router = APIRouter(prefix="/sessions", tags=["Sessions"])

@router.post("", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
def create_session(session_in: SessionCreate, db: DBSession = Depends(get_db)):
    return session_service.create_session(db, session_in)

@router.get("", response_model=List[SessionResponse])
def read_sessions(skip: int = 0, limit: int = 100, db: DBSession = Depends(get_db)):
    return session_service.get_all_sessions(db, skip=skip, limit=limit)

@router.get("/{id}", response_model=SessionDetailResponse)
def read_session(id: str, db: DBSession = Depends(get_db)):
    return session_service.get_session(db, id)

@router.put("/{id}", response_model=SessionResponse)
def update_session(id: str, session_in: SessionUpdate, db: DBSession = Depends(get_db)):
    return session_service.update_session(db, id, session_in)

@router.delete("/{id}", response_model=SessionResponse)
def delete_session(id: str, db: DBSession = Depends(get_db)):
    return session_service.delete_session(db, id)
