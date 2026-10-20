import os
from pathlib import Path
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session as DBSession
from loguru import logger

from app.models.presentation import Presentation
from app.models.employee_list import EmployeeList
from app.models.session import Session
from app.storage.local_storage import local_storage

class AssetMatcher:
    def find_duplicate_presentation(self, db: DBSession, file_hash: str) -> Optional[Presentation]:
        if not file_hash:
            return None
        from app.core.security.secure_storage import secure_storage
        candidates = db.query(Presentation).filter(Presentation.file_hash == file_hash).all()
        for pres in candidates:
            if pres and local_storage.exists(pres.storage_path):
                # Verify asset is readable with current master key before reusing
                try:
                    with secure_storage.open_decrypted_file(pres):
                        return pres
                except Exception as err:
                    logger.warning(f"AssetMatcher | Candidate presentation id={pres.id} cannot be decrypted ({err}). Skipping reuse.")
        return None

    def find_duplicate_employee_list(self, db: DBSession, file_hash: str) -> Optional[EmployeeList]:
        if not file_hash:
            return None
        from app.core.security.secure_storage import secure_storage
        candidates = db.query(EmployeeList).filter(EmployeeList.file_hash == file_hash).all()
        for emp in candidates:
            if emp and local_storage.exists(emp.storage_path):
                # Verify asset is readable with current master key before reusing
                try:
                    with secure_storage.open_decrypted_file(emp):
                        return emp
                except Exception as err:
                    logger.warning(f"AssetMatcher | Candidate employee list id={emp.id} cannot be decrypted ({err}). Skipping reuse.")
        return None

asset_matcher = AssetMatcher()
