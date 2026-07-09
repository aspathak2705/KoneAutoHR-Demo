import json
from pathlib import Path
from app.modules.induction.package.schema import (
    InductionPackage,
    SessionMetadataSchema,
    EmployeeProfileSchema,
    AudienceSummarySchema,
    WelcomeFlowSchema,
    SlideKnowledgeSchema,
    SlideNarrationSchema,
    ClosingScriptSchema,
    SessionStateSchema
)

def build_and_save_package(
    session_id: str,
    session_metadata: dict,
    meeting_context: dict,
    employee_profiles: list[dict],
    audience_summary: dict,
    slide_knowledge: list[dict],
    scripts: dict,
    session_dir: Path
) -> dict:
    """
    Builds the Pydantic InductionPackage structure, validates it, and saves it.
    """
    # 1. Construct Schema Components
    meta_schema = SessionMetadataSchema(
        session_id=session_id,
        name=session_metadata["name"],
        company_name=meeting_context["company_name"],
        department=meeting_context["department"],
        scheduled_at=session_metadata.get("scheduled_at"),
        language=meeting_context["language"],
        session_type=meeting_context["session_type"]
    )

    profiles_schema = [EmployeeProfileSchema(**p) for p in employee_profiles]

    audience_schema = AudienceSummarySchema(
        total_employees=audience_summary["total_employees"],
        audience_type=audience_summary["audience_type"],
        departments_represented=audience_summary["departments_represented"],
        new_hires_count=audience_summary["new_hires_count"],
        technical_level=audience_summary["technical_level"]
    )

    welcome_schema = WelcomeFlowSchema(
        greeting=scripts["welcome_flow"]["greeting"],
        wait_message=scripts["welcome_flow"]["wait_message"],
        audio_check=scripts["welcome_flow"]["audio_check"],
        ice_breaker=scripts["welcome_flow"]["ice_breaker"],
        agenda=scripts["welcome_flow"]["agenda"]
    )

    slide_knowledge_schema = [SlideKnowledgeSchema(**s) for s in slide_knowledge]

    slide_narrations_schema = {}
    for slide_num, narr_data in scripts["slide_narrations"].items():
        slide_narrations_schema[str(slide_num)] = SlideNarrationSchema(
            slide_number=narr_data["slide_number"],
            narration=narr_data["narration"],
            transition=narr_data.get("transition"),
            interactive_prompt=narr_data.get("interactive_prompt"),
            expected_questions=narr_data.get("expected_questions", [])
        )

    closing_schema = ClosingScriptSchema(
        summary=scripts["closing_script"]["summary"],
        congratulations=scripts["closing_script"]["congratulations"],
        next_steps=scripts["closing_script"]["next_steps"]
    )

    state_schema = SessionStateSchema(
        current_slide=1,
        status="prepared",
        progress=0.0
    )

    # 2. Build final Package
    package = InductionPackage(
        session_metadata=meta_schema,
        meeting_context=meeting_context,
        employee_profiles=profiles_schema,
        audience_summary=audience_schema,
        welcome_flow=welcome_schema,
        slide_knowledge=slide_knowledge_schema,
        slide_narrations=slide_narrations_schema,
        closing_script=closing_schema,
        session_state=state_schema
    )

    # 3. Save to disk
    package_path = session_dir / "induction_package.json"
    with open(package_path, "w", encoding="utf-8") as f:
        f.write(package.model_dump_json(indent=2))

    return package.model_dump()
