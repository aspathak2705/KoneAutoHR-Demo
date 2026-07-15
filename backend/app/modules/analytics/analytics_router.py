from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session as DBSession
from typing import List, Dict, Any
from app.db.database import get_db
from app.modules.analytics.analytics_service import analytics_service

router = APIRouter(prefix="/analytics", tags=["Analytics & Reports"])

@router.get("/dashboard", response_model=Dict[str, Any])
def get_dashboard_summary(db: DBSession = Depends(get_db)):
    return analytics_service.get_dashboard_summary(db)

@router.get("/runs", response_model=List[Dict[str, Any]])
def get_runs(db: DBSession = Depends(get_db)):
    return analytics_service.get_runs(db)
