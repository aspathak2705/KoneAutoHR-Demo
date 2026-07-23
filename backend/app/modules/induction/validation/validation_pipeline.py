import json
import datetime
from pathlib import Path
from sqlalchemy.orm import Session as DBSession
from app.modules.induction.validation.validation_engine import validation_engine

class ValidationPipeline:
    def execute(
        self,
        db: DBSession,
        presentation_id: str,
        employee_list_id: str,
        session_id: str,
        session_dir: Path
    ) -> dict:
        """
        Runs validation checks on inputs and outputs a validation report.
        """
        report_path = session_dir / "validation_report.json"
        session_dir.mkdir(parents=True, exist_ok=True)

        errors = []
        ppt_path = None
        excel_path = None
        presenter_profile = {}

        try:
            ppt_path, excel_path, presenter_profile = validation_engine.validate_inputs(
                db, presentation_id, employee_list_id
            )
        except Exception as e:
            errors.append(str(e))

        report = {
            "timestamp": datetime.datetime.now().isoformat(),
            "session_id": session_id,
            "presentation_id": presentation_id,
            "employee_list_id": employee_list_id,
            "validation_passed": len(errors) == 0,
            "presenter_profile_valid": bool(presenter_profile),
            "presentation_deck_valid": ppt_path is not None and len(errors) == 0,
            "employee_list_valid": excel_path is not None and len(errors) == 0,
            "errors": errors,
            "details": {
                "ppt_path": ppt_path,
                "excel_path": excel_path,
                "presenter_profile": presenter_profile
            }
        }

        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)

        if not report["validation_passed"]:
            raise ValueError(f"Validation Pipeline failed: {', '.join(errors)}")

        return report

validation_pipeline = ValidationPipeline()
