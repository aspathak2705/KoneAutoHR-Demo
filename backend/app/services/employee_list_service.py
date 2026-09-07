from sqlalchemy.orm import Session as DBSession
from typing import List, Optional
from fastapi import UploadFile
from app.repositories.employee_list_repository import employee_list_repository
from app.models.employee_list import EmployeeList
from app.services.storage_service import storage_service
from app.modules.induction.employees.excel_parser import parse_employees_excel
from app.db.unit_of_work import UnitOfWork

class EmployeeListService:
    def get_all(self, db: DBSession, skip: int = 0, limit: int = 100) -> List[EmployeeList]:
        return employee_list_repository.get_all(db, skip, limit)

    def get(self, db: DBSession, id: str) -> Optional[EmployeeList]:
        return employee_list_repository.get(db, id)

    async def create_employee_list(self, db: DBSession, name: str, file: UploadFile) -> EmployeeList:
        from app.storage.local_storage import local_storage
        from app.storage.asset_matcher import asset_matcher
        
        # Calculate upload hash before saving
        file_hash = await local_storage.calculate_upload_hash(file)
        
        # Check for existing duplicate employee list
        existing_emp = asset_matcher.find_duplicate_employee_list(db, file_hash)
        if existing_emp:
            from loguru import logger
            logger.info(f"EmployeeListService | Reusing existing employee list id={existing_emp.id} for hash={file_hash}")
            return existing_emp

        # If new file, save to storage
        sanitized, storage_path, size, file_hash = await local_storage.save_file(file, "employee_lists")
        
        # Profile employee count
        try:
            full_path = local_storage.get_path(storage_path)
            employees = parse_employees_excel(str(full_path))
            employee_count = len(employees)
        except Exception:
            employee_count = 0

        with UnitOfWork(db):
            res = employee_list_repository.create(
                db,
                name=name,
                original_filename=file.filename,
                storage_path=storage_path,
                employee_count=employee_count,
                file_hash=file_hash
            )
            
        # Refresh the employee list object to populate database-generated defaults
        db.refresh(res)
        return res

    def update(self, db: DBSession, id: str, **kwargs) -> EmployeeList:
        emp = employee_list_repository.get(db, id)
        if not emp:
            raise ValueError(f"Employee list with id {id} not found")
        with UnitOfWork(db):
            res = employee_list_repository.update(db, emp, **kwargs)
        db.refresh(res)
        return res

    def delete(self, db: DBSession, id: str) -> Optional[EmployeeList]:
        from app.storage.cleanup_service import cleanup_service
        emp = employee_list_repository.get(db, id)
        if not emp:
            return None
            
        if not cleanup_service.can_delete_employee_list(db, id):
            ref_count = cleanup_service.get_employee_list_reference_count(db, id)
            raise ValueError(f"Cannot delete employee list: currently referenced by {ref_count} session(s).")
            
        cleanup_service.cleanup_unreferenced_employee_list(db, id)
        return emp

employee_list_service = EmployeeListService()
