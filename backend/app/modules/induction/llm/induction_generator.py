from app.modules.induction.llm.introduction_generator import generate_introduction
from app.modules.induction.llm.narration_generator import generate_narration
from app.modules.induction.llm.transition_generator import generate_transition
from app.modules.induction.llm.question_generator import generate_expected_questions
from app.modules.induction.llm.closing_generator import generate_closing

async def generate_induction_package_scripts(
    session_metadata: dict,
    meeting_context: dict,
    audience_summary: dict,
    slide_knowledge: list[dict]
) -> dict:
    """
    Orchestrates individual generators to compile all scripts and Q&A schemas.
    """
    # 1. Welcome / Intro Flow
    welcome_data = await generate_introduction(
        session_metadata=session_metadata,
        meeting_context=meeting_context,
        audience_summary=audience_summary,
        slide_knowledge=slide_knowledge
    )

    # 2. Slide narrations, transitions, and predicted questions
    slide_narrations = {}

    for idx, slide in enumerate(slide_knowledge):
        slide_number = slide["slide_number"]

        # Narration & Interactive Check
        narr = await generate_narration(slide, audience_summary, meeting_context)

        # Transition (if not last slide)
        trans_text = None
        if idx < len(slide_knowledge) - 1:
            next_slide = slide_knowledge[idx + 1]
            trans = await generate_transition(slide, next_slide)
            trans_text = trans.get("transition")

        # Q&A predictions
        questions_data = await generate_expected_questions(slide, audience_summary, meeting_context)
        expected_q = questions_data.get("expected_questions", [])

        slide_narrations[slide_number] = {
            "slide_number": slide_number,
            "narration": narr.get("narration", ""),
            "transition": trans_text,
            "interactive_prompt": narr.get("interactive_prompt"),
            "expected_questions": expected_q
        }

    # 3. Closing script
    closing_data = await generate_closing(meeting_context, audience_summary)

    return {
        "welcome_flow": welcome_data,
        "slide_narrations": slide_narrations,
        "closing_script": closing_data
    }
