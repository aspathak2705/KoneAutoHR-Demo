from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession
from typing import List, Dict, Any
from pathlib import Path
from loguru import logger

from app.models.session import Session
from app.models.employee_list import EmployeeList
from app.models.presentation import Presentation
from app.models.presentation_metadata import PresentationMetadata
from app.modules.induction.employees.excel_parser import parse_employees_excel

class AnalyticsService:
    def get_dashboard_summary(self, db: DBSession) -> Dict[str, Any]:
        total_sessions = db.query(Session).count()
        completed_sessions = db.query(Session).filter(Session.status == "COMPLETED").count()
        
        # Calculate unique employees and departments across completed sessions
        completed_runs = db.query(Session).filter(Session.status == "COMPLETED").all()
        unique_employees = set()
        unique_departments = set()
        
        for run in completed_runs:
            if run.employee_list and run.employee_list.storage_path:
                excel_path = Path(run.employee_list.storage_path)
                if excel_path.exists():
                    try:
                        employees = parse_employees_excel(str(excel_path))
                        for emp in employees:
                            # Use email or name as unique key
                            emp_id = emp.get("email") or emp.get("name")
                            if emp_id:
                                unique_employees.add(emp_id.lower().strip())
                            
                            dept = emp.get("department")
                            if dept and str(dept).strip():
                                unique_departments.add(str(dept).strip().lower())
                    except Exception as e:
                        logger.warning(f"Error parsing excel in analytics dashboard for list {run.employee_list.id}: {e}")
                        # Fallback to adding the aggregate count
                        unique_employees.add(f"fallback_batch_{run.employee_list.id}")
                else:
                    # File missing, fall back to list employee_count aggregate
                    unique_employees.add(f"fallback_batch_{run.employee_list.id}")

        employees_count = len(unique_employees)
        # If fallback aggregates were added, adjust the count
        fallback_batches = [x for x in unique_employees if x.startswith("fallback_batch_")]
        if fallback_batches:
            employees_count -= len(fallback_batches)
            for batch in fallback_batches:
                batch_id = batch.replace("fallback_batch_", "")
                emp_list = db.query(EmployeeList).filter(EmployeeList.id == batch_id).first()
                if emp_list:
                    employees_count += emp_list.employee_count

        departments_count = len(unique_departments)
        departments_val = str(departments_count) if departments_count > 0 else "Not Available"

        compliance_rate = 0
        if total_sessions > 0:
            compliance_rate = int(round((completed_sessions / total_sessions) * 100))

        return {
            "total_inductions": total_sessions,
            "employees_onboarded": employees_count,
            "departments_covered": departments_val,
            "compliance_rate": compliance_rate
        }

    def get_runs(self, db: DBSession) -> List[Dict[str, Any]]:
        sessions = db.query(Session).order_by(Session.created_at.desc()).all()
        runs = []
        for s in sessions:
            presentation_name = s.presentation.name if s.presentation else "N/A"
            employees_count = s.employee_list.employee_count if s.employee_list else 0
            
            runs.append({
                "id": s.id,
                "title": s.name,
                "presentation": presentation_name,
                "employees": employees_count,
                "created": s.created_at.strftime("%Y-%m-%d %H:%M"),
                "status": s.status,
                "meeting": "",
                "duration": ""
            })
        return runs

analytics_service = AnalyticsService()
