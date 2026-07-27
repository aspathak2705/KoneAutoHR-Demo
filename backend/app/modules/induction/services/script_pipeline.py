import json
import logging
from pathlib import Path
from sqlalchemy.orm import Session as DBSession
from app.modules.induction.llm.preparation_orchestrator import generate_induction_package_scripts
from app.repositories.presentation_script_repository import presentation_script_repository
from app.repositories.presentation_question_repository import presentation_question_repository
from app.db.unit_of_work import UnitOfWork

logger = logging.getLogger(__name__)

class ScriptPipeline:
    async def execute(self, db: DBSession, structured_context: dict, session_dir: Path) -> dict:
        """
        Consumes structured context ONLY to generate AI scripts.
        Registers generated script/faq in the database, and saves output as session_script.json.
        """
        session_metadata = {
            "name": structured_context["session"]["name"],
            "scheduled_at": structured_context["session"]["scheduled_at"]
        }
        
        meeting_context = structured_context["presenter_profile"]
        employee_profiles = structured_context["audience"]["profiles"]
        audience_summary = structured_context["audience"]["summary"]
        slide_knowledge = structured_context["presentation"]["slides"]

        # Call LLM generation orchestrator
        logger.info("SCRIPT PIPELINE: Calling generate_induction_package_scripts")

        scripts = await generate_induction_package_scripts(
            session_metadata=session_metadata,
            meeting_context=meeting_context,
            employee_profiles=employee_profiles,
            audience_summary=audience_summary,
            slide_knowledge=slide_knowledge
        )
        logger.info("PACKAGE GENERATED")
        

        logger.info("SCRIPT PIPELINE: LLM generation completed")

        presentation_id = structured_context["session"].get("presentation_id")
        
        # Save script/faq in database
        with UnitOfWork(db):
            presentation_script_repository.create(
                db=db,
                presentation_id=presentation_id,
                script_content=json.dumps(scripts),
                llm_model="nvidia/nemotron-3-super-120b-a12b:free"
            )
            logger.info("SCRIPT SAVED")
            presentation_question_repository.create(
                db=db,
                presentation_id=presentation_id,
                questions_content=json.dumps(scripts.get("faq", []))
            )
            logger.info("QUESTIONS SAVED")
        script_path = session_dir / "session_script.json"
        with open(script_path, "w", encoding="utf-8") as f:
            json.dump(scripts, f, indent=2)

        return scripts

script_pipeline = ScriptPipeline()
