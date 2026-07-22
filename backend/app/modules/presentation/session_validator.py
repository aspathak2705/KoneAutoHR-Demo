import datetime
from typing import List
from loguru import logger
from app.modules.presentation.session_script_models import SessionScript, ScriptValidationResult

class SessionValidator:
    """
    Session Validation Phase
    Validates completeness and determinism of generated SessionScript before runtime starts.
    Checks:
    - Greeting exists
    - Closing exists
    - Q&A handoff exists
    - Every slide accounted for
    - Every section has transition
    - No orphan slides
    """
    def validate(self, script: SessionScript, expected_slide_count: int = 1) -> ScriptValidationResult:
        issues: List[str] = []
        step_types = [s.type for s in script.steps]

        if "GREETING" not in step_types:
            issues.append("Missing required GREETING step.")
        if "CLOSING" not in step_types:
            issues.append("Missing required CLOSING step.")
        if "WAIT_FOR_QUESTIONS" not in step_types:
            issues.append("Missing required WAIT_FOR_QUESTIONS Q&A handoff step.")

        # Check slide steps coverage
        slide_steps = [s for s in script.steps if s.type == "SHOW_SLIDE"]
        found_slides = set(s.slide_number for s in slide_steps if s.slide_number is not None)

        for i in range(1, expected_slide_count + 1):
            if i not in found_slides:
                issues.append(f"Orphan/missing slide narration for Slide {i}.")

        # Check section transitions
        section_steps = [s for s in script.steps if s.type == "PRESENTATION_SECTION"]
        for sec in section_steps:
            if not sec.transition and not sec.speech:
                issues.append(f"Section '{sec.section_title}' missing spoken transition.")

        is_valid = len(issues) == 0
        script.validated = is_valid
        script.validation_issues = issues

        if is_valid:
            logger.info(f"SessionValidator | Session script for {script.session_id} passed validation cleanly.")
        else:
            logger.warning(f"SessionValidator | Session script for {script.session_id} failed validation: {issues}")

        return ScriptValidationResult(
            is_valid=is_valid,
            issues=issues,
            checked_at=datetime.datetime.now().isoformat()
        )

session_validator = SessionValidator()
