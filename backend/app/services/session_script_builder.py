import json
import os
from typing import Dict, Any, List
from sqlalchemy.orm import Session as DBSession
from loguru import logger
from app.modules.induction.llm.client import llm_client

class SessionScriptBuilder:
    """
    Phase 4 — Session Script Builder
    Assembles input context (PPT, Employee metadata, Presenter config), calls LLM to generate the unified Session JSON.
    """
    async def build_session_script(
        self,
        company_name: str,
        voice_persona: str,
        employee_profiles: List[Dict[str, Any]],
        slide_knowledge: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        logger.info("SessionScriptBuilder | Constructing session script prompt...")

        # Extract employee highlights
        emp_names = []
        emp_depts = set()
        for emp in employee_profiles[:10]:
            emp_names.append(emp.get("name", "Team Member"))
            if emp.get("department"):
                emp_depts.add(emp.get("department"))
        
        employees_str = ", ".join(emp_names) if emp_names else "new hires"
        depts_str = ", ".join(emp_depts) if emp_depts else "various departments"

        # Load Prompt Template using Jinja2
        from jinja2 import Template
        prompt_dir = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "modules",
            "induction",
            "prompts"
        )
        template_path = os.path.join(prompt_dir, "session_generation.jinja")
        if os.path.exists(template_path):
            with open(template_path, "r", encoding="utf-8") as f:
                template = Template(f.read())
        else:
            template = Template("Please generate a session script for company {{ company_name }}.")

        slides_str = json.dumps(slide_knowledge, indent=2)
        prompt = template.render(
            company_name=company_name,
            departments=depts_str,
            employees=employees_str,
            slides=slides_str,
            voice_persona=voice_persona
        )

        try:
            payload = await llm_client.generate_json(prompt, name="session_script")
            logger.info("SessionScriptBuilder | Session script generated successfully.")
            return payload
        except Exception as e:
            logger.error(f"SessionScriptBuilder | Script generation failure: {e}. Falling back to default session payload.")
            return self._get_fallback_payload(company_name, employees_str, depts_str, slide_knowledge)

    def _get_fallback_payload(
        self,
        company_name: str,
        employees: str,
        departments: str,
        slide_knowledge: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        slides = []
        for s in slide_knowledge:
            slide_num = s.get("slide_number", 1)
            title = s.get("title", f"Slide {slide_num}")
            slides.append({
                "slide_number": slide_num,
                "title": title,
                "objective": f"Introduce {title} to new employees.",
                "transition_in": f"Let's move onto the next topic: {title}.",
                "narration": f"Here we cover the core aspects of {title}. {s.get('content', '')}",
                "understanding_check": f"Do you have any questions about {title}?",
                "transition_out": f"That concludes our discussion on {title}.",
                "video_prompt": None,
                "quiz_question": None
            })

        if not slides:
            slides = [{
                "slide_number": 1,
                "title": "Welcome",
                "objective": "Introduce company values.",
                "transition_in": "Let's get started.",
                "narration": f"Welcome to {company_name}. We prioritize innovation and safety.",
                "understanding_check": "Are there any questions?",
                "transition_out": "Moving on.",
                "video_prompt": None,
                "quiz_question": None
            }]

        return {
            "opening": {
                "greeting": f"Good morning everyone! Welcome to today's {company_name} onboarding session.",
                "presenter_intro": f"I am your AI HR Trainer, here to guide you through your induction.",
                "employee_welcome": f"A warm welcome to our new team members: {employees}.",
                "audio_check": "Before we begin, can everyone hear me clearly?",
                "ice_breaker": f"Please type your department in the chat box. I see we have people from {departments}!",
                "session_rules": "Please keep your mic muted and post questions in the chat box.",
                "agenda": "Today we will cover company values, safety policies, and key onboarding steps."
            },
            "slides": slides,
            "closing": {
                "summary": "To summarize, we covered KONE's values, safety rules, and your direct next steps.",
                "next_steps": "Please complete your mandatory training portal items by the end of this week.",
                "farewell": "Thank you all for your time! Welcome to the KONE family, and have a great day!"
            }
        }

session_script_builder = SessionScriptBuilder()
