from typing import Dict, Any, Optional
from app.modules.induction.llm.client import llm_client
from app.core.config import settings
from loguru import logger

class GreetingAgent:
    async def generate_welcome(
        self,
        employee: Dict[str, Any],
        presenter: Dict[str, Any],
        opening_script: Dict[str, Any]
    ) -> str:
        """
        Generates welcome statement personalized for the new hire joiner.
        """
        trainer_name = presenter.get("ai_trainer_name", "KONE Trainer")
        company = presenter.get("company_name", "KONE")
        emp_name = employee.get("name", "Team Member")
        emp_role = employee.get("role", "New Hire")
        emp_dept = employee.get("department", "General")

        prompt = f"""
        Generate a warm, professional onboarding greeting welcoming a new hire.
        Trainer: {trainer_name} representing {company}
        Employee: {emp_name} joining as {emp_role} in the {emp_dept} department.
        Base script template to use:
        Greeting: "{opening_script.get('greeting', '')}"
        Presenter Intro: "{opening_script.get('presenter_intro', '')}"
        Employee Welcome: "{opening_script.get('employee_welcome', '')}"
        Rules: "{opening_script.get('session_rules', '')}"
        Agenda: "{opening_script.get('agenda', '')}"
        
        Respond ONLY in the following JSON format:
        {{
            "greeting_text": "Complete conversational paragraph welcome script"
        }}
        """
        
        if settings.LLM_API_KEY:
            try:
                res = await llm_client.generate_json(prompt, name="greeting_agent")
                text = res.get("greeting_text")
                if text:
                    logger.info("GreetingAgent | Generated personalized greeting via LLM.")
                    return text
            except Exception as e:
                logger.error(f"GreetingAgent | LLM generation failed: {e}. Falling back to template.")

        # Deterministic fallback
        fallback = (
            f"{opening_script.get('greeting', 'Hello!')} I am {trainer_name} from {company}. "
            f"A warm welcome to {emp_name} joining us as {emp_role} in {emp_dept}. "
            f"Here are the rules: {opening_script.get('session_rules', '')}. "
            f"Today we will cover: {opening_script.get('agenda', '')}."
        )
        logger.info("GreetingAgent | Loaded template-based greeting fallback.")
        return fallback

greeting_agent = GreetingAgent()
