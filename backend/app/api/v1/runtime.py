from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session as DBSession
from app.db.database import get_db

router = APIRouter(prefix="/runtime", tags=["Orchestration Runtime"])

@router.get("/{session_id}", status_code=status.HTTP_501_NOT_IMPLEMENTED)
def get_runtime_state(session_id: str, db: DBSession = Depends(get_db)):
    raise HTTPException(status_code=501, detail="Resource not prepared")
