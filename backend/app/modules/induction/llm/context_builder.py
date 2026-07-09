def build_llm_context(
    meeting_context: dict,
    audience_summary: dict,
    ai_persona: dict,
    slide: dict = None
) -> dict:
    """
    Combines sub-contexts into a single, unified context dictionary for LLM generators.
    """
    context = {
        "meeting_context": meeting_context,
        "audience_summary": audience_summary,
        "ai_persona": ai_persona
    }
    if slide:
        context["slide"] = slide
    return context
