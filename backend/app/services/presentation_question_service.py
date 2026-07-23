import json
import datetime
from sqlalchemy.orm import Session as DBSession
from typing import Optional
from app.repositories.presentation_repository import presentation_repository
from app.repositories.presentation_question_repository import presentation_question_repository
from app.repositories.employee_list_repository import employee_list_repository
from app.models.presentation_question import PresentationQuestion
from app.modules.induction.parser.ppt_parser import parse_presentation
from app.modules.induction.employees.excel_parser import parse_employees_excel
from app.modules.induction.employees.profiler import profile_employees
from app.modules.induction.employees.audience_builder import build_audience_summary
from app.db.unit_of_work import UnitOfWork

class PresentationQuestionService:
    async def generate_questions_only(
        self, db: DBSession, presentation_id: str, employee_list_id: str
    ) -> PresentationQuestion:
        pres = presentation_repository.get(db, presentation_id)
        if not pres:
            raise ValueError("Presentation not found")
        emp = employee_list_repository.get(db, employee_list_id)
        if not emp:
            raise ValueError("Employee list not found")

        from app.modules.configuration.configuration_service import configuration_service
        config = configuration_service.get_active_config(db)
        if not config:
            raise ValueError("Organization profile is not configured yet. Please complete the Profile page before preparing AI content.")

        company_name = config.company_name

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
                "trainer_name": f"{company_name} AI Trainer",
                "objectives": f"New Hire Induction for {pres.name}",
                "ai_officer_name": config.ai_officer_name,
                "ai_role_description": config.ai_role_description,
                "vocal_tone": config.vocal_tone,
                "communication_style": config.communication_style
            }
            
            from app.modules.induction.llm.context_builder import build_llm_context
            from app.modules.induction.llm.faq_generator import generate_faq
            
            ai_persona = {
                "name": config.ai_officer_name,
                "role": config.ai_role_description,
                "tone": config.vocal_tone,
                "communication_style": config.communication_style,
                "company": company_name
            }
            
            base_context = build_llm_context(
                session_metadata=session_metadata,
                meeting_context=meeting_context,
                employee_profiles=employee_profiles,
                audience_summary=audience_summary,
                slide_knowledge=slide_knowledge,
                ai_persona=ai_persona
            )
            
            faq_data = await generate_faq(base_context)
            faq_payload = faq_data.get("faq", [])
            
            with UnitOfWork(db):
                res = presentation_question_repository.create(
                    db,
                    presentation_id=presentation_id,
                    questions_content=json.dumps(faq_payload)
                )
            return res

    def get_active_questions(self, db: DBSession, presentation_id: str) -> Optional[PresentationQuestion]:
        return presentation_question_repository.get_active(db, presentation_id)

    def update_questions(self, db: DBSession, question_id: str, questions_content: list) -> PresentationQuestion:
        q = presentation_question_repository.get(db, question_id)
        if not q:
            raise ValueError("Questions record not found")
        with UnitOfWork(db):
            res = presentation_question_repository.update(db, q, questions_content=json.dumps(questions_content))
        return res

presentation_question_service = PresentationQuestionService()
