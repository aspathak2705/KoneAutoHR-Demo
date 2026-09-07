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

    def audit_storage(self, db: DBSession, cleanup: bool = False) -> Dict[str, Any]:
        """
        Audits physical storage vs DB records:
        - Detects missing physical files referenced in DB
        - Detects unreferenced/orphan files in storage/uploads
        - Performs safe cleanup if cleanup=True
        """
        presentations = db.query(Presentation).all()
        employee_lists = db.query(EmployeeList).all()

        missing_physical = []
        referenced_files = set()

        for pres in presentations:
            if pres.storage_path:
                full_p = local_storage.get_path(pres.storage_path)
                referenced_files.add(str(full_p.resolve()))
                if not full_p.exists():
                    missing_physical.append({"type": "presentation", "id": pres.id, "path": pres.storage_path})

        for emp in employee_lists:
            if emp.storage_path:
                full_p = local_storage.get_path(emp.storage_path)
                referenced_files.add(str(full_p.resolve()))
                if not full_p.exists():
                    missing_physical.append({"type": "employee_list", "id": emp.id, "path": emp.storage_path})

        # Scan storage directories for orphan physical files
        orphan_files = []
        for category_dir in [local_storage.get_path("presentations"), local_storage.get_path("employee_lists")]:
            if category_dir.exists():
                for f in category_dir.glob("*"):
                    if f.is_file() and str(f.resolve()) not in referenced_files:
                        orphan_files.append(str(f))

        cleaned_orphans = []
        if cleanup:
            for orphan in orphan_files:
                try:
                    os.remove(orphan)
                    cleaned_orphans.append(orphan)
                except Exception as err:
                    logger.error(f"CleanupService | Failed to delete orphan file {orphan}: {err}")

        encrypted_count = sum(1 for p in presentations if getattr(p, "encryption_version", 0) > 0) + \
                          sum(1 for e in employee_lists if getattr(e, "encryption_version", 0) > 0)
        legacy_count = (len(presentations) + len(employee_lists)) - encrypted_count

        return {
            "total_presentations": len(presentations),
            "total_employee_lists": len(employee_lists),
            "encrypted_assets": encrypted_count,
            "legacy_plaintext_assets": legacy_count,
            "missing_physical_files": missing_physical,
            "orphan_files": orphan_files,
            "cleaned_orphans": cleaned_orphans if cleanup else [],
            "dry_run": not cleanup
        }

cleanup_service = CleanupService()
