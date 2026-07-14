from fastapi import APIRouter, Depends, UploadFile, File, Form, status, HTTPException
from sqlalchemy.orm import Session as DBSession
from typing import List
from app.db.database import get_db
from app.schemas.employee_list import EmployeeListResponse
from app.services.employee_list_service import employee_list_service

router = APIRouter(prefix="/employee-lists", tags=["Saved Employee Lists"])

@router.get("", response_model=List[EmployeeListResponse])
def get_employee_lists(skip: int = 0, limit: int = 100, db: DBSession = Depends(get_db)):
    return employee_list_service.get_all(db, skip, limit)

@router.post("", response_model=EmployeeListResponse, status_code=status.HTTP_201_CREATED)
async def upload_employee_list(
    name: str = Form(...),
    file: UploadFile = File(...),
    db: DBSession = Depends(get_db)
):
    try:
        return await employee_list_service.create_employee_list(db, name, file)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/{id}", response_model=EmployeeListResponse)
def delete_employee_list(id: str, db: DBSession = Depends(get_db)):
    emp = employee_list_service.delete(db, id)
    if not emp:
        raise HTTPException(status_code=404, detail="Employee list not found")
    return emp
