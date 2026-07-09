from app.modules.induction.llm.context_builder import build_llm_context
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
    Orchestrates individual generators using a unified context builder to compile all scripts.
    """
    # 1. Define AI Persona
    ai_persona = {
        "name": "KONE AI Induction Officer",
        "role": "HR Induction Officer",
        "tone": "Professional, Friendly",
        "communication_style": "Conversational",
        "company": "KONE"
    }

    # 2. Build Base Context
    base_context = build_llm_context(
        meeting_context=meeting_context,
        audience_summary=audience_summary,
        ai_persona=ai_persona
    )

    # 3. Generate Welcome / Intro Flow
    welcome_data = await generate_introduction(base_context, slide_knowledge)

    # 4. Slide narrations, transitions, and predicted questions
    slide_narrations = {}

    for idx, slide in enumerate(slide_knowledge):
        slide_number = slide["slide_number"]

        # Build slide-specific context
        slide_context = build_llm_context(
            meeting_context=meeting_context,
            audience_summary=audience_summary,
            ai_persona=ai_persona,
            slide=slide
        )

        # Narration & Interactive Check
        narr = await generate_narration(slide_context)

        # Transition (if not last slide)
        trans_text = None
        if idx < len(slide_knowledge) - 1:
            next_slide = slide_knowledge[idx + 1]
            trans = await generate_transition(base_context, slide, next_slide)
            trans_text = trans.get("transition")

        # Q&A predictions
        questions_data = await generate_expected_questions(slide_context)
        expected_q = questions_data.get("expected_questions", [])

        # Format VideoScript if slide contains videos
        video_script = None
        if slide.get("videos"):
            # If the LLM returned video_script in narration response, use it
            if narr.get("video_script"):
                video_script = narr["video_script"]
            else:
                video_script = {
                    "before_video": f"Before we watch this video on '{slide['title']}', please take note of KONE's approach to collaboration.",
                    "after_video": "I hope that video gave you a clearer understanding. Do you have any questions so far?",
                    "pause_after_video": True,
                    "resume_message": "Now, let's continue with the rest of the presentation."
                }

        slide_narrations[slide_number] = {
            "slide_number": slide_number,
            "narration": narr.get("narration", ""),
            "transition": trans_text,
            "interactive_prompt": narr.get("interactive_prompt"),
            "learning_objective": narr.get("learning_objective", f"Understand {slide['title']} and related KONE guidelines."),
            "key_takeaways": narr.get("key_takeaways", [f"Core requirements of {slide['title']}."]),
            "story_example": narr.get("story_example"),
            "video_script": video_script,
            "expected_questions": expected_q
        }

    # 5. Closing script
    closing_data = await generate_closing(base_context)

    return {
        "ai_persona": ai_persona,
        "welcome_flow": welcome_data,
        "slide_narrations": slide_narrations,
        "closing_script": closing_data
    }
