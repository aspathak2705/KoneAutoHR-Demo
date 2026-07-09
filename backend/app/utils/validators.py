import os
from fastapi import HTTPException, status

def validate_presentation_file(filename: str):
    ext = os.path.splitext(filename)[1].lower()
    if ext not in [".ppt", ".pptx"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file format for presentation. Only .ppt and .pptx allowed."
        )

def validate_employee_list_file(filename: str):
    ext = os.path.splitext(filename)[1].lower()
    if ext not in [".xls", ".xlsx"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file format for employee list. Only .xls and .xlsx allowed."
        )
