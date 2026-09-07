import os
from pathlib import Path
from typing import Dict, Any, List
from sqlalchemy.orm import Session as DBSession
from loguru import logger

from app.models.presentation import Presentation
from app.models.employee_list import EmployeeList
from app.models.session import Session
from app.storage.local_storage import local_storage

class CleanupService:
    def get_presentation_reference_count(self, db: DBSession, presentation_id: str) -> int:
        return db.query(Session).filter(Session.presentation_id == presentation_id).count()

    def get_employee_list_reference_count(self, db: DBSession, employee_list_id: str) -> int:
        return db.query(Session).filter(Session.employee_list_id == employee_list_id).count()

    def can_delete_presentation(self, db: DBSession, presentation_id: str) -> bool:
        return self.get_presentation_reference_count(db, presentation_id) == 0

    def can_delete_employee_list(self, db: DBSession, employee_list_id: str) -> bool:
        return self.get_employee_list_reference_count(db, employee_list_id) == 0

    def cleanup_unreferenced_presentation(self, db: DBSession, presentation_id: str) -> bool:
        pres = db.query(Presentation).filter(Presentation.id == presentation_id).first()
        if not pres:
            return False
        if not self.can_delete_presentation(db, presentation_id):
            logger.warning('CleanupService | Cannot delete presentation %s: still referenced.' % presentation_id)
            return False
        if pres.storage_path:
            local_storage.delete(pres.storage_path)
        db.delete(pres)
        db.commit()
        logger.info('CleanupService | Deleted presentation %s.' % presentation_id)
        return True

    def cleanup_unreferenced_employee_list(self, db: DBSession, employee_list_id: str) -> bool:
        emp = db.query(EmployeeList).filter(EmployeeList.id == employee_list_id).first()
        if not emp:
            return False
        if not self.can_delete_employee_list(db, employee_list_id):
            logger.warning('CleanupService | Cannot delete employee list %s: still referenced.' % employee_list_id)
            return False
        if emp.storage_path:
            local_storage.delete(emp.storage_path)
        db.delete(emp)
        db.commit()
        logger.info('CleanupService | Deleted employee list %s.' % employee_list_id)
        return True

cleanup_service = CleanupService()
