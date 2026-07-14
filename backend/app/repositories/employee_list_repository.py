from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession
from typing import List, Optional
from app.models.employee_list import EmployeeList

class EmployeeListRepository:
    def get(self, db: DBSession, id: str) -> Optional[EmployeeList]:
        stmt = select(EmployeeList).where(EmployeeList.id == id)
        return db.scalars(stmt).first()

    def get_all(self, db: DBSession, skip: int = 0, limit: int = 100) -> List[EmployeeList]:
        stmt = select(EmployeeList).order_by(EmployeeList.uploaded_at.desc()).offset(skip).limit(limit)
        return list(db.scalars(stmt).all())

    def create(self, db: DBSession, name: str, original_filename: str, storage_path: str, employee_count: int = 0) -> EmployeeList:
        db_obj = EmployeeList(
            name=name,
            original_filename=original_filename,
            storage_path=storage_path,
            employee_count=employee_count
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def update(self, db: DBSession, db_obj: EmployeeList, **kwargs) -> EmployeeList:
        for key, value in kwargs.items():
            setattr(db_obj, key, value)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def delete(self, db: DBSession, id: str) -> Optional[EmployeeList]:
        db_obj = self.get(db, id)
        if db_obj:
            db.delete(db_obj)
            db.commit()
        return db_obj

employee_list_repository = EmployeeListRepository()
