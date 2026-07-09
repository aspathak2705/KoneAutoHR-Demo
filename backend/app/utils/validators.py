import os
from app.core.exceptions import InvalidUploadException

def validate_presentation_file(filename: str):
    ext = os.path.splitext(filename)[1].lower()
    if ext not in [".ppt", ".pptx"]:
        raise InvalidUploadException("Invalid file format for presentation. Only .ppt and .pptx allowed.")

def validate_employee_list_file(filename: str):
    ext = os.path.splitext(filename)[1].lower()
    if ext not in [".xls", ".xlsx"]:
        raise InvalidUploadException("Invalid file format for employee list. Only .xls and .xlsx allowed.")
