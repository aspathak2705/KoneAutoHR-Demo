import json
import datetime
from sqlalchemy.orm import Session as DBSession
from typing import Optional
from app.repositories.presentation_repository import presentation_repository
from app.repositories.presentation_script_repository import presentation_script_repository
from app.repositories.presentation_question_repository import presentation_question_repository
from app.repositories.presentation_metadata_repository import presentation_metadata_repository
from app.repositories.employee_list_repository import employee_list_repository
from app.models.presentation_script import PresentationScript
from app.modules.induction.parser.ppt_parser import parse_presentation
from app.modules.induction.employees.excel_parser import parse_employees_excel
from app.modules.induction.employees.profiler import profile_employees
from app.modules.induction.employees.audience_builder import build_audience_summary
from app.core.config import settings

class PresentationScriptService:
    async def generate_script_and_questions(
        self, db: DBSession, presentation_id: str, employee_list_id: str, company_name: str = "KONE"
    ) -> PresentationScript:
        pres = presentation_repository.get(db, presentation_id)
        if not pres:
            raise ValueError("Presentation not found")
        emp = employee_list_repository.get(db, employee_list_id)
        if not emp:
            raise ValueError("Employee list not found")

        import tempfile
        from pathlib import Path
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            slide_knowledge = parse_presentation(pres.storage_path, temp_path)
            
            raw_rows = parse_employees_excel(emp.storage_path)
            employee_profiles = profile_employees(raw_rows)
            audience_summary = build_audience_summary(employee_profiles)
            
            session_metadata = {
                "name": pres.name,
                "scheduled_at": None
            }
            
            meeting_context = {
                "company_name": company_name,
                "department": "HR",
                "trainer_name": "KONE AI Trainer",
                "objectives": f"New Hire Induction for {pres.name}"
            }
            
            from app.modules.induction.llm.preparation_orchestrator import generate_induction_package_scripts
            scripts = await generate_induction_package_scripts(
                session_metadata=session_metadata,
                meeting_context=meeting_context,
                employee_profiles=employee_profiles,
                audience_summary=audience_summary,
                slide_knowledge=slide_knowledge
            )
            
            # 1. Update metadata
            meta = presentation_metadata_repository.get_by_presentation(db, presentation_id)
            if meta:
                presentation_metadata_repository.update(
                    db,
                    meta,
                    slide_count=len(slide_knowledge),
                    generation_date=datetime.datetime.now(),
                    generation_status="COMPLETED",
                    last_ai_generation=datetime.datetime.now()
                )
                
            # 2. Save PresentationScript (WelcomeFlow, SlideNarrations, Closing)
            script_payload = {
                "welcome_flow": scripts.get("welcome_flow"),
                "slide_narrations": scripts.get("slide_narrations"),
                "closing_script": scripts.get("closing_script")
            }
            script_row = presentation_script_repository.create(
                db,
                presentation_id=presentation_id,
                script_content=json.dumps(script_payload),
                llm_model=settings.LLM_MODEL
            )
            
            # 3. Save PresentationQuestion (FAQ list)
            faq_payload = scripts.get("faq", [])
            presentation_question_repository.create(
                db,
                presentation_id=presentation_id,
                questions_content=json.dumps(faq_payload)
            )
            
            return script_row

    def get_active_script(self, db: DBSession, presentation_id: str) -> Optional[PresentationScript]:
        return presentation_script_repository.get_active(db, presentation_id)

    def update_script(self, db: DBSession, script_id: str, script_content: dict) -> PresentationScript:
        script = presentation_script_repository.get(db, script_id)
        if not script:
            raise ValueError("Script not found")
        return presentation_script_repository.update(db, script, script_content=json.dumps(script_content))

presentation_script_service = PresentationScriptService()
