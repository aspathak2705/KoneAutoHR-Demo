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
        pres = db.query(Presentation).filter(Presentation.file_hash == file_hash).first()
        if pres and local_storage.exists(pres.storage_path):
            return pres
        return None

    def find_duplicate_employee_list(self, db: DBSession, file_hash: str) -> Optional[EmployeeList]:
        if not file_hash:
            return None
        emp = db.query(EmployeeList).filter(EmployeeList.file_hash == file_hash).first()
        if emp and local_storage.exists(emp.storage_path):
            return emp
        return None

asset_matcher = AssetMatcher()
