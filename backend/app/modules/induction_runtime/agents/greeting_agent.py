from typing import Dict, Any, Optional
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
        Always returns deterministic greetings to guarantee consistency and minimize latency.
        """
        trainer_name = presenter.get("ai_trainer_name", "KONE Trainer")
        company = presenter.get("company_name", "KONE")
        emp_name = employee.get("name", "Team Member")
        emp_role = employee.get("role", "New Hire")
        emp_dept = employee.get("department", "General")

        greeting = opening_script.get("greeting", "Hello and welcome!")
        intro = opening_script.get("presenter_intro", "I am your AI HR Trainer {trainer_name}, here to guide you today.")
        rules = opening_script.get("session_rules", "Please stay muted during slides and use chat for questions.")
        agenda = opening_script.get("agenda", "Today we will cover company values, safety policies, and key onboarding steps.")

        # Structured welcome greeting delivery
        welcome_text = (
            f"{greeting} {intro} "
            f"A very warm welcome to {emp_name}, joining us as {emp_role} in the {emp_dept} department! "
            f"Before we begin, here are the session guidelines: {rules} "
            f"For our agenda today: {agenda} Let's get started."
        )
        
        # Replace layout placeholders globally across all greeting parts
        welcome_text = welcome_text.replace("{trainer_name}", trainer_name).replace("{company_name}", company)
        
        logger.info("GreetingAgent | Generated deterministic welcome greeting with resolved placeholders.")
        return welcome_text

greeting_agent = GreetingAgent()
