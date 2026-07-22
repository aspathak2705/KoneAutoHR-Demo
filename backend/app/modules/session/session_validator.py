import datetime
import os
from typing import List, Dict, Any
from sqlalchemy.orm import Session as DBSession
from loguru import logger
from app.modules.presentation.session_script_models import SessionScript, ScriptValidationResult
from app.modules.assets.asset_manager import asset_manager
from app.modules.assets.asset_registry import asset_registry
from app.models.employee_list import EmployeeList
from app.models.organization_config import OrganizationConfig

class SessionValidator:
    """
    Module 10 — Validation Phase
    Validates completeness and consistency of script, employee list, presentation files, and organizer configs before runtime starts.
    """
    def validate_pre_runtime(
        self,
        db: DBSession,
        script: SessionScript,
        presentation_id: str,
        employee_list_id: str
    ) -> ScriptValidationResult:
        issues: List[str] = []

        # 1. Validate Organizer/Presenter Profile
        config = db.query(OrganizationConfig).first()
        if not config or not config.company_name:
            issues.append("Presenter profile (OrganizationConfig) is not configured.")

        # 2. Validate Employee Sheet
        emp_list = db.query(EmployeeList).filter(EmployeeList.id == employee_list_id).first()
        if not emp_list or not os.path.exists(emp_list.storage_path):
            issues.append("Employee list sheet file does not exist or storage path is missing.")

        # 3. Validate Presentation Asset Existence
        assets = asset_registry.get_presentation_assets(db, presentation_id)
        pres_assets = [a for a in assets if a.asset_type == "presentation"]
        if not pres_assets:
            # Fallback path check
            from app.models.presentation import Presentation
            pres = db.query(Presentation).filter(Presentation.id == presentation_id).first()
            if not pres or not os.path.exists(pres.storage_path):
                issues.append("Presentation template file does not exist in resolved storage provider.")
        else:
            try:
                asset_manager.resolve(db, pres_assets[0].asset_id)
            except Exception as e:
                issues.append(f"Failed to resolve presentation asset storage path: {e}")

        # 4. Validate Script Completeness
        step_types = [s.type for s in script.steps]
        if "GREETING" not in step_types:
            issues.append("Missing required GREETING step.")
        if "CLOSING" not in step_types:
            issues.append("Missing required CLOSING step.")
        if "WAIT_FOR_QUESTIONS" not in step_types:
            issues.append("Missing required WAIT_FOR_QUESTIONS Q&A handoff step.")

        is_valid = len(issues) == 0
        script.validated = is_valid
        script.validation_issues = issues

        if is_valid:
            logger.info(f"SessionValidator | Pre-runtime validation passed cleanly for session {script.session_id}.")
        else:
            logger.warning(f"SessionValidator | Pre-runtime validation failed for session {script.session_id}: {issues}")

        return ScriptValidationResult(
            is_valid=is_valid,
            issues=issues,
            checked_at=datetime.datetime.now().isoformat()
        )

session_validator = SessionValidator()
