from sqlalchemy.orm import Session as DBSession
from typing import List, Optional
from fastapi import UploadFile
from app.repositories.employee_list_repository import employee_list_repository
from app.models.employee_list import EmployeeList
from app.services.storage_service import storage_service
from app.modules.induction.employees.excel_parser import parse_employees_excel

class EmployeeListService:
    def get_all(self, db: DBSession, skip: int = 0, limit: int = 100) -> List[EmployeeList]:
        return employee_list_repository.get_all(db, skip, limit)

    def get(self, db: DBSession, id: str) -> Optional[EmployeeList]:
        return employee_list_repository.get(db, id)

    async def create_employee_list(self, db: DBSession, name: str, file: UploadFile) -> EmployeeList:
        sanitized, storage_path, size = await storage_service.save_employee_list_file(file)
        
        # Profile employee count
        try:
            employees = parse_employees_excel(storage_path)
            employee_count = len(employees)
        except Exception:
            employee_count = 0

        return employee_list_repository.create(
            db,
            name=name,
            original_filename=file.filename,
            storage_path=storage_path,
            employee_count=employee_count
        )

    def update(self, db: DBSession, id: str, **kwargs) -> EmployeeList:
        emp = employee_list_repository.get(db, id)
        if not emp:
            raise ValueError(f"Employee list with id {id} not found")
        return employee_list_repository.update(db, emp, **kwargs)

    def delete(self, db: DBSession, id: str) -> Optional[EmployeeList]:
        # Delete from disk
        emp = employee_list_repository.get(db, id)
        if emp and emp.storage_path:
            import os
            try:
                os.remove(emp.storage_path)
            except OSError:
                pass
        return employee_list_repository.delete(db, id)

employee_list_service = EmployeeListService()
