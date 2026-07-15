import asyncio
from app.modules.induction.llm.context_builder import build_llm_context
from app.modules.induction.llm.introduction_generator import generate_introduction
from app.modules.induction.llm.slide_generator import generate_slide_elements
from app.modules.induction.llm.faq_generator import generate_faq
from app.modules.induction.llm.closing_generator import generate_closing

async def generate_induction_package_scripts(
    session_metadata: dict,
    meeting_context: dict,
    employee_profiles: list[dict],
    audience_summary: dict,
    slide_knowledge: list[dict]
) -> dict:
    """
    Orchestrates welcome flow, slide narrations, FAQ, and closing script generators using the Master Context Contract.
    Assumes all generators return validated output structures.
    """
    # 1. Define AI Persona
    company_name = meeting_context.get("company_name", "KONE")
    ai_persona = {
        "name": f"{company_name} AI Induction Officer",
        "role": "HR Induction Officer",
        "tone": "Professional, Friendly",
        "communication_style": "Conversational",
        "company": company_name
    }

    # 2. Build Base Context
    base_context = build_llm_context(
        session_metadata=session_metadata,
        meeting_context=meeting_context,
        employee_profiles=employee_profiles,
        audience_summary=audience_summary,
        slide_knowledge=slide_knowledge,
        ai_persona=ai_persona
    )

    # 3. Generate Welcome / Intro Flow (1 call)
    welcome_data = await generate_introduction(base_context)

    # 4. Generate all slides concurrently (1 call per slide) with a Semaphore
    sem = asyncio.Semaphore(5)
    slide_narrations = {}

    async def process_slide(slide: dict, idx: int) -> tuple[int, dict]:
        async with sem:
            next_slide = slide_knowledge[idx + 1] if idx < len(slide_knowledge) - 1 else None
            slide_context = build_llm_context(
                session_metadata=session_metadata,
                meeting_context=meeting_context,
                employee_profiles=employee_profiles,
                audience_summary=audience_summary,
                slide_knowledge=slide_knowledge,
                ai_persona=ai_persona,
                slide=slide,
                next_slide=next_slide
            )
            res = await generate_slide_elements(slide_context)
            return slide["slide_number"], res

    tasks = [process_slide(slide, idx) for idx, slide in enumerate(slide_knowledge)]
    results = await asyncio.gather(*tasks)

    for slide_number, res in results:
        # Access validated properties directly (expected_questions removed)
        slide_narrations[slide_number] = {
            "slide_number": slide_number,
            "narration": res["narration"],
            "transition": res.get("transition"),
            "interactive_prompt": res["interactive_prompt"],
            "learning_objective": res["learning_objective"],
            "key_takeaways": res["key_takeaways"],
            "story_example": res.get("story_example"),
            "video_script": res.get("video_script")
        }

    # 5. Generate Global FAQ (1 call)
    faq_data = await generate_faq(base_context)

    # 6. Closing script (1 call)
    closing_data = await generate_closing(base_context)

    return {
        "ai_persona": ai_persona,
        "welcome_flow": welcome_data,
        "slide_narrations": slide_narrations,
        "faq": faq_data.get("faq", []),
        "closing_script": closing_data
    }
