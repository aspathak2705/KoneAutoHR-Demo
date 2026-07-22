import json
import datetime
from typing import Dict, Any, List
from sqlalchemy.orm import Session as DBSession
from loguru import logger

from app.modules.induction.llm.client import llm_client
from app.services.runtime_context_service import runtime_context_service
from app.modules.presentation.session_validator import session_validator
from app.modules.presentation.session_script_models import (
    SessionScript,
    ScriptStep,
    CompletionRule,
    FallbackRule,
    CompleteWhenRule
)

class SessionScriptGenerator:
    """
    Enhanced Version 2.2 — Session Script Generator
    Addresses Gaps 1-4:
    - Gap 1: HR Objective Driven Prompting (LLM acts as HR Director conducting induction).
    - Gap 2: Employee Personalization (extracts names, departments, roles, locations from Employee List).
    - Gap 3: Presenter Personality Voice Encoding (incorporates presenter profile tone/formality).
    - Gap 4: Dynamic Periodic Waiting Messages for attendee waiting phase.
    """
    def generate_session_script(self, db: DBSession, session_id: str) -> SessionScript:
        logger.info(f"SessionScriptGenerator | Generating personalized HR Induction Blueprint for {session_id}...")
        ctx = runtime_context_service.build_runtime_context(db, session_id)
        
        company_name = "KONE"
        presenter_name = "KONE AutoHR Trainer"

        # Gap 3: Presenter Personality Profile
        presenter_prof = ctx.get("presenter_profile")
        presenter_tone = "warm, encouraging, professional, with natural pacing"
        if presenter_prof and hasattr(presenter_prof, "voice_persona"):
            presenter_tone = presenter_prof.voice_persona or presenter_tone

        # Gap 2: Employee Data Personalization
        emp_asset = ctx.get("employees_asset")
        emp_summary = []
        dept_set = set()
        if emp_asset and hasattr(emp_asset, "employee_list") and isinstance(emp_asset.employee_list, list):
            for e in emp_asset.employee_list[:6]:
                name = e.get("name", "Team Member")
                dept = e.get("department", "Engineering")
                role = e.get("designation", "Specialist")
                dept_set.add(dept)
                emp_summary.append(f"{name} ({role}, {dept})")

        dept_str = ", ".join(dept_set) if dept_set else "Engineering, HR, Manufacturing"
        emp_str = ", ".join(emp_summary) if emp_summary else "Akash, Riya, Priya"

        # Slides Info
        pres_asset = ctx.get("presentation_asset")
        slides_data = []
        if pres_asset and hasattr(pres_asset, "slide_content") and isinstance(pres_asset.slide_content, list):
            for i, s in enumerate(pres_asset.slide_content, 1):
                slides_data.append({
                    "slide_number": i,
                    "slide_id": f"slide_{i}",
                    "title": s.get("title", f"Slide {i}"),
                    "content": s.get("content", s.get("text", ""))
                })

        if not slides_data:
            slides_data = [
                {"slide_number": 1, "slide_id": "slide_1", "title": "Welcome to KONE", "content": "Company Overview and Values"},
                {"slide_number": 2, "slide_id": "slide_2", "title": "Workplace Safety & Policies", "content": "Safety First, Code of Conduct, and Benefits"}
            ]

        # Gap 1: HR Objective Prompting
        prompt = f"""
You are an expert HR Director at {company_name}. Conduct a complete, personalized employee induction session.
Presenter Persona & Voice: {presenter_name} ({presenter_tone}).
Employee Batch Joining Info:
- Departments Represented: {dept_str}
- Sample New Attendees: {emp_str}
Slides Deck Info: {json.dumps(slides_data)}

Generate spoken sentences personalized to these attendees. Return a JSON object with:
1. "greeting": Array of 2 pre-generated spoken sentences mentioning company and welcoming attendees.
2. "introduction": Array of 2 pre-generated spoken sentences introducing presenter and acknowledging departments like {dept_str}.
3. "audio_check": Array of 1 spoken sentence.
4. "session_rules": Array of 2 spoken sentences.
5. "ice_breaker": Array of 2 spoken sentences asking attendees from {dept_str} to post in chat.
6. "waiting_speeches": Array of 2 periodic spoken waiting messages (e.g. "We will begin in 1 minute as colleagues join.", "Almost ready...").
7. "sections": Array of section objects. Each section has:
   - "title": Section title
   - "slides": Array of slide numbers
   - "learning_objective": Objective
   - "transition": Spoken transition sentence
   - "slide_scripts": Object mapping slide number to:
     - "before": Array of 1 sentence before showing slide
     - "during": Array of 2 sentences explaining slide
     - "after": Array of 1 sentence after slide
8. "understanding_check": Array of 1 question sentence.
9. "summary": Array of 2 spoken sentences.
10. "closing": Array of 2 spoken sentences.
"""
        generated = {}
        try:
            raw_response = llm_client.generate(prompt)
            json_match = raw_response
            if "```json" in raw_response:
                json_match = raw_response.split("```json")[1].split("```")[0].strip()
            elif "```" in raw_response:
                json_match = raw_response.split("```")[1].split("```")[0].strip()
            generated = json.loads(json_match)
        except Exception as e:
            logger.warning(f"SessionScriptGenerator | LLM JSON fallback: {e}")
            generated = {
                "greeting": [
                    f"Good morning everyone! Welcome to today's {company_name} new employee induction session.",
                    f"We are thrilled to welcome our new colleagues joining us today!"
                ],
                "introduction": [
                    f"My name is {presenter_name}, your digital HR trainer.",
                    f"I see team members joining across {dept_str}. Welcome aboard!"
                ],
                "audio_check": ["Before we begin, can everyone hear my voice clearly?"],
                "session_rules": [
                    "Please keep your microphone muted unless speaking to prevent audio feedback.",
                    "Feel free to use the Teams chat box at any time for your questions."
                ],
                "ice_breaker": [
                    "To kick things off, let's do a quick warm-up!",
                    f"Please type your name and department ({dept_str}) in the chat box."
                ],
                "waiting_speeches": [
                    "We will begin our session shortly as colleagues continue joining the meeting.",
                    "Almost ready! Waiting for a few more attendees to settle in."
                ],
                "sections": [
                    {
                        "title": "Company Overview & Safety Policies",
                        "slides": [s["slide_number"] for s in slides_data],
                        "learning_objective": f"Understand {company_name} core values and workplace safety.",
                        "transition": "Now let's turn to our core induction presentation.",
                        "slide_scripts": {
                            str(s["slide_number"]): {
                                "before": [f"Turning to Slide {s['slide_number']}: {s['title']}."],
                                "during": [
                                    f"This section details {s['content']}.",
                                    f"At {company_name}, excellence and safety are our top priorities."
                                ],
                                "after": ["Please take a moment to review these points."]
                            } for s in slides_data
                        }
                    }
                ],
                "understanding_check": ["Does anyone have any quick questions about our safety policies before we proceed?"],
                "summary": [
                    f"To summarize, {company_name} is committed to safety, innovation, and people development.",
                    "Your HR contacts and leaders are always here to support your success."
                ],
                "closing": [
                    f"Thank you all for attending KONE's induction program today.",
                    "Welcome aboard, and we wish you a great career at KONE!"
                ]
            }

        # Gap 4: Periodic Waiting Messages in Fallback
        waiting_speeches = generated.get("waiting_speeches", [
            "We will begin shortly as colleagues continue joining.",
            "Almost ready! Waiting for a few more attendees to join."
        ])

        steps: List[ScriptStep] = [
            ScriptStep(
                step_id=1,
                type="WAIT_FOR_PARTICIPANTS",
                duration=120,
                mandatory=True,
                completion=CompletionRule(attendance_percent=80.0, timeout_seconds=60),
                fallback=FallbackRule(
                    speak=waiting_speeches[0],
                    periodic_speeches=waiting_speeches
                ),
                complete_when=CompleteWhenRule(timeout=60)
            ),
            ScriptStep(
                step_id=2,
                type="GREETING",
                speech=generated.get("greeting", []),
                complete_when=CompleteWhenRule(speech_completed=True)
            ),
            ScriptStep(
                step_id=3,
                type="INTRODUCTION",
                speech=generated.get("introduction", []),
                complete_when=CompleteWhenRule(speech_completed=True)
            ),
            ScriptStep(
                step_id=4,
                type="AUDIO_CHECK",
                speech=generated.get("audio_check", []),
                complete_when=CompleteWhenRule(thumbs_up=True, timeout=20)
            ),
            ScriptStep(
                step_id=5,
                type="SESSION_RULES",
                speech=generated.get("session_rules", []),
                complete_when=CompleteWhenRule(speech_completed=True)
            ),
            ScriptStep(
                step_id=6,
                type="ICE_BREAKER",
                duration=90,
                mandatory=True,
                can_skip=False,
                expected_response="chat",
                speech=generated.get("ice_breaker", []),
                complete_when=CompleteWhenRule(responses=3, timeout=60)
            )
        ]

        # Grouped presentation sections
        sections = generated.get("sections", [])
        for sec in sections:
            sec_title = sec.get("title", "Presentation Section")
            sec_slides = sec.get("slides", [])
            sec_trans = sec.get("transition", "Now let's proceed to the next section.")

            steps.append(ScriptStep(
                step_id=len(steps) + 1,
                type="PRESENTATION_SECTION",
                section_title=sec_title,
                slides=sec_slides,
                learning_objective=sec.get("learning_objective"),
                transition=sec_trans,
                speech=[sec_trans]
            ))

            slide_scripts = sec.get("slide_scripts", {})
            for s_num in sec_slides:
                s_info = slide_scripts.get(str(s_num)) or slide_scripts.get(s_num) or {}
                before_sentences = s_info.get("before", [f"Moving to slide {s_num}."])
                during_sentences = s_info.get("during", [f"Explaining slide {s_num} content."])
                after_sentences = s_info.get("after", ["Any quick questions on this slide?"])

                steps.append(ScriptStep(
                    step_id=len(steps) + 1,
                    type="SHOW_SLIDE",
                    slide_id=f"slide_{s_num}",
                    slide_number=s_num,
                    presentation_asset="presentation.json",
                    speech_id=f"speech_slide_{s_num}",
                    before=before_sentences,
                    during=during_sentences,
                    after=after_sentences,
                    speech=before_sentences + during_sentences + after_sentences,
                    complete_when=CompleteWhenRule(speech_completed=True)
                ))

        steps.extend([
            ScriptStep(
                step_id=len(steps) + 1,
                type="UNDERSTANDING_CHECK",
                speech=generated.get("understanding_check", []),
                complete_when=CompleteWhenRule(timeout=20)
            ),
            ScriptStep(
                step_id=len(steps) + 1,
                type="SUMMARY",
                speech=generated.get("summary", []),
                complete_when=CompleteWhenRule(speech_completed=True)
            ),
            ScriptStep(
                step_id=len(steps) + 1,
                type="WAIT_FOR_QUESTIONS",
                speech=["We will now open the floor for your live Q&A session."],
                complete_when=CompleteWhenRule(speech_completed=True)
            ),
            ScriptStep(
                step_id=len(steps) + 1,
                type="CLOSING",
                speech=generated.get("closing", []),
                complete_when=CompleteWhenRule(speech_completed=True)
            ),
            ScriptStep(
                step_id=len(steps) + 1,
                type="LEAVE_MEETING"
            )
        ])

        script = SessionScript(
            session_id=session_id,
            company_name=company_name,
            presenter_name=presenter_name,
            generated_at=datetime.datetime.now().isoformat(),
            steps=steps
        )

        # Run Validation Phase
        session_validator.validate(script, expected_slide_count=len(slides_data))
        logger.info(f"SessionScriptGenerator | Script for {session_id} validated: {script.validated}")
        return script

session_script_generator = SessionScriptGenerator()
