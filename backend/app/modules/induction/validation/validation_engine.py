import os
from pathlib import Path
from sqlalchemy.orm import Session as DBSession
from app.repositories.presentation_repository import presentation_repository
from app.repositories.employee_list_repository import employee_list_repository
from app.modules.configuration.configuration_service import configuration_service
from app.modules.induction.employees.excel_parser import parse_employees_excel
from pptx import Presentation

class ValidationEngine:
    def validate_inputs(self, db: DBSession, presentation_id: str, employee_list_id: str) -> tuple[str, str, dict]:
        """
        Validates PPT presentation, Employee Excel sheet, and active Presenter Profile.
        Returns:
            tuple[str, str, dict]: (ppt_path, excel_path, presenter_profile_dict)
        """
        # 1. Validate Presenter Profile (Organization Config)
        config = configuration_service.get_active_config(db)
        if not config:
            raise ValueError(
                "Organization profile is not configured yet. "
                "Please complete the Profile setup page before preparing induction."
            )

        presenter_profile = {
            "company_name": config.company_name,
            "ai_officer_name": config.ai_officer_name,
            "ai_role_description": config.ai_role_description,
            "vocal_tone": config.vocal_tone,
            "communication_style": config.communication_style
        }

        # 2. Validate Presentation file
        pres = presentation_repository.get(db, presentation_id)
        if not pres:
            raise ValueError(f"Presentation with ID {presentation_id} not found in database.")
        
        ppt_path = Path(pres.storage_path)
        if not ppt_path.exists() or ppt_path.stat().st_size == 0:
            raise ValueError(f"PowerPoint file is missing or corrupted at {pres.storage_path}")

        try:
            # Test slide reading
            prs = Presentation(str(ppt_path))
            if len(prs.slides) == 0:
                raise ValueError("PowerPoint deck has zero slides.")
        except Exception as e:
            raise ValueError(f"Failed to read PowerPoint file. It may be corrupted. Error: {e}")

        # 3. Validate Employee List file
        emp = employee_list_repository.get(db, employee_list_id)
        if not emp:
            raise ValueError(f"Employee list with ID {employee_list_id} not found in database.")

        excel_path = Path(emp.storage_path)
        if not excel_path.exists() or excel_path.stat().st_size == 0:
            raise ValueError(f"Employee list Excel file is missing or corrupted at {emp.storage_path}")

        try:
            # Test parsing rows
            rows = parse_employees_excel(str(excel_path))
            if len(rows) == 0:
                raise ValueError("Employee list is empty.")
            
            # Check required fields
            for idx, r in enumerate(rows):
                if not r.get("name") or not r.get("email"):
                    raise ValueError(f"Malformed row at index {idx}: Name or Email column is blank.")
        except Exception as e:
            raise ValueError(f"Failed to parse employee Excel sheet. Error: {e}")

        return str(ppt_path.resolve()), str(excel_path.resolve()), presenter_profile

validation_engine = ValidationEngine()
