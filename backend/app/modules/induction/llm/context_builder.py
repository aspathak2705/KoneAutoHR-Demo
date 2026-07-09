def build_llm_context(
    session_metadata: dict,
    meeting_context: dict,
    employee_profiles: list,
    audience_summary: dict,
    slide_knowledge: list,
    ai_persona: dict,
    slide: dict = None,
    next_slide: dict = None
) -> dict:
    """
    Master Context Contract.

    Every LLM generator receives this object.

    Never bypass Context Builder.

    Never manually rebuild context.

    This guarantees prompt consistency across
    all generators.
    """
    context = {
        "session_metadata": session_metadata,
        "meeting_context": meeting_context,
        "employee_profiles": employee_profiles,
        "audience_summary": audience_summary,
        "slide_knowledge": slide_knowledge,
        "ai_persona": ai_persona,
        "slide": slide,
        "next_slide": next_slide
    }

    # Task 7 - Context Validation
    required = [
        "session_metadata",
        "meeting_context",
        "audience_summary",
        "ai_persona",
        "slide_knowledge"
    ]

    for key in required:
        if context.get(key) is None:
            raise ValueError(f"Required context field '{key}' is missing or None.")

    return context
