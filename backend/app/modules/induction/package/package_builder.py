import json
import datetime
from pathlib import Path
from app.modules.induction.package.schema import (
    InductionPackage,
    SessionMetadataSchema,
    AIPersonaSchema,
    EmployeeProfileSchema,
    AudienceSummarySchema,
    WelcomeFlowSchema,
    SlideKnowledgeSchema,
    SlideNarrationSchema,
    VideoScriptSchema,
    FAQItemSchema,
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
    Assumes all scripts fields are fully validated and populated.
    """
    # 1. AI Persona Schema
    ai_persona_schema = AIPersonaSchema(
        name=scripts["ai_persona"]["name"],
        role=scripts["ai_persona"]["role"],
        tone=scripts["ai_persona"]["tone"],
        communication_style=scripts["ai_persona"]["communication_style"],
        company=scripts["ai_persona"]["company"]
    )

    # 2. Metadata Schema
    prepared_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
    meta_schema = SessionMetadataSchema(
        session_id=session_id,
        name=session_metadata["name"],
        company_name=meeting_context["company_name"],
        department=meeting_context["department"],
        scheduled_at=session_metadata.get("scheduled_at"),
        language=meeting_context["language"],
        session_type=meeting_context["session_type"],
        meeting_duration=60,
        timezone="UTC",
        company_domain=meeting_context.get("company_domain", "kone.com"),
        prepared_at=prepared_at,
        prepared_by_version="1.0.0"
    )

    # 3. Profiles & Audience Summary
    profiles_schema = [EmployeeProfileSchema(**p) for p in employee_profiles]

    audience_schema = AudienceSummarySchema(
        total_employees=audience_summary["total_employees"],
        audience_type=audience_summary["audience_type"],
        departments_represented=audience_summary["departments_represented"],
        new_hires_count=audience_summary["new_hires_count"],
        technical_level=audience_summary["technical_level"]
    )

    # 4. Welcome Flow Schema
    welcome_schema = WelcomeFlowSchema(
        greeting=scripts["welcome_flow"]["greeting"],
        wait_message=scripts["welcome_flow"]["wait_message"],
        audio_check=scripts["welcome_flow"]["audio_check"],
        ice_breaker=scripts["welcome_flow"]["ice_breaker"],
        agenda=scripts["welcome_flow"]["agenda"],
        meeting_join_message=scripts["welcome_flow"]["meeting_join_message"],
        participant_wait_timeout=scripts["welcome_flow"]["participant_wait_timeout"],
        late_joiner_message=scripts["welcome_flow"]["late_joiner_message"],
        start_confirmation=scripts["welcome_flow"]["start_confirmation"]
    )

    # 5. Slide Knowledge Schema
    slide_knowledge_schema = [SlideKnowledgeSchema(**s) for s in slide_knowledge]

    # 6. Slide Narrations (Q&A Removed from individual slides)
    slide_narrations_schema = {}
    for slide_num, narr_data in scripts["slide_narrations"].items():
        # Map video script if exists
        video_schema = None
        if narr_data.get("video_script") is not None:
            video_schema = VideoScriptSchema(
                before_video=narr_data["video_script"]["before_video"],
                after_video=narr_data["video_script"]["after_video"],
                pause_after_video=narr_data["video_script"]["pause_after_video"],
                resume_message=narr_data["video_script"]["resume_message"]
            )

        slide_narrations_schema[str(slide_num)] = SlideNarrationSchema(
            slide_number=narr_data["slide_number"],
            narration=narr_data["narration"],
            transition=narr_data.get("transition"),
            interactive_prompt=narr_data["interactive_prompt"],
            learning_objective=narr_data["learning_objective"],
            key_takeaways=narr_data["key_takeaways"],
            story_example=narr_data.get("story_example"),
            video_script=video_schema
        )

    # 7. Global FAQ Schema
    faq_schema = []
    for q in scripts.get("faq", []):
        faq_schema.append(FAQItemSchema(
            question=q["question"],
            answer=q["answer"],
            confidence=q.get("confidence", 1.0),
            references=q.get("references", [])
        ))

    # 8. Closing Script Schema
    closing_schema = ClosingScriptSchema(
        summary=scripts["closing_script"]["summary"],
        congratulations=scripts["closing_script"]["congratulations"],
        next_steps=scripts["closing_script"]["next_steps"]
    )

    # 9. Session State Schema
    state_schema = SessionStateSchema(
        current_slide=1,
        status="prepared",
        progress=0.0
    )

    # 10. Build final package
    package = InductionPackage(
        schema_version="1.0",
        package_version="1.0",
        session_metadata=meta_schema,
        meeting_context=meeting_context,
        ai_persona=ai_persona_schema,
        employee_profiles=profiles_schema,
        audience_summary=audience_schema,
        welcome_flow=welcome_schema,
        slide_knowledge=slide_knowledge_schema,
        slide_narrations=slide_narrations_schema,
        faq=faq_schema,
        closing_script=closing_schema,
        session_state=state_schema
    )

    # 11. Save to disk
    package_path = session_dir / "induction_package.json"
    with open(package_path, "w", encoding="utf-8") as f:
        f.write(package.model_dump_json(indent=2))

    return package.model_dump()
