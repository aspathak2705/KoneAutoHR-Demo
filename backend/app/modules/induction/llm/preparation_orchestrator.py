import asyncio
from app.modules.induction.llm.context_builder import build_llm_context
from app.modules.induction.llm.introduction_generator import generate_introduction
from app.modules.induction.llm.slide_generator import generate_slide_elements
from app.modules.induction.llm.closing_generator import generate_closing

async def generate_induction_package_scripts(
    session_metadata: dict,
    meeting_context: dict,
    employee_profiles: list[dict],
    audience_summary: dict,
    slide_knowledge: list[dict]
) -> dict:
    """
    Orchestrates introduction, slide details, and closing script generators using the Master Context Contract.
    """
    # 1. Define AI Persona
    ai_persona = {
        "name": "KONE AI Induction Officer",
        "role": "HR Induction Officer",
        "tone": "Professional, Friendly",
        "communication_style": "Conversational",
        "company": "KONE"
    }

    # 2. Build Base Context (using the unified Master Context Builder)
    base_context = build_llm_context(
        session_metadata=session_metadata,
        meeting_context=meeting_context,
        employee_profiles=employee_profiles,
        audience_summary=audience_summary,
        slide_knowledge=slide_knowledge,
        ai_persona=ai_persona
    )

    # 3. Generate Welcome / Intro Flow (1 call passing full context)
    welcome_data = await generate_introduction(base_context)

    # 4. Generate all slides concurrently (1 call per slide) with a Semaphore
    sem = asyncio.Semaphore(5)
    slide_narrations = {}

    async def process_slide(slide: dict, idx: int) -> tuple[int, dict]:
        async with sem:
            next_slide = slide_knowledge[idx + 1] if idx < len(slide_knowledge) - 1 else None
            # Build slide-specific context using the unified Master Context Builder
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
        # Standardize video script structure if slide contains videos
        video_script = res.get("video_script")
        target_slide = next(s for s in slide_knowledge if s["slide_number"] == slide_number)
        if target_slide.get("videos") and not video_script:
            video_script = {
                "before_video": f"Before we watch this video on '{target_slide['title']}', please take note of our core guidelines.",
                "after_video": "I hope that video gave you a clearer understanding. Do you have any questions so far?",
                "pause_after_video": True,
                "resume_message": "Now, let's continue with the rest of the presentation."
            }

        slide_narrations[slide_number] = {
            "slide_number": slide_number,
            "narration": res.get("narration", ""),
            "transition": res.get("transition"),
            "interactive_prompt": res.get("interactive_prompt"),
            "learning_objective": res.get("learning_objective", f"Understand {target_slide['title']} and related KONE guidelines."),
            "key_takeaways": res.get("key_takeaways", [f"Core requirements of {target_slide['title']}."]),
            "story_example": res.get("story_example"),
            "video_script": video_script,
            "expected_questions": res.get("expected_questions", [])
        }

    # 5. Closing script (1 call passing full context)
    closing_data = await generate_closing(base_context)

    return {
        "ai_persona": ai_persona,
        "welcome_flow": welcome_data,
        "slide_narrations": slide_narrations,
        "closing_script": closing_data
    }
