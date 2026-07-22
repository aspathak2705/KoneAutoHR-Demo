from typing import Dict, Any, List
from sqlalchemy.orm import Session as DBSession
from loguru import logger
from app.services.runtime_context_service import runtime_context_service
from app.modules.presentation.models import PresentationSession, SlideData

class PresentationSessionService:
    """
    Stage 2 — Presentation Session Builder
    Builds PresentationSession from RuntimeContext (Presentation Asset, Script, FAQs, Company Config).
    """
    def build_presentation_session(self, db: DBSession, session_id: str) -> PresentationSession:
        context = runtime_context_service.build_runtime_context(db, session_id)
        pres_asset = context.get("presentation_asset")
        script = context.get("presentation_script")
        meeting = context.get("meeting")

        slides: List[SlideData] = []
        if pres_asset and hasattr(pres_asset, "slide_content") and isinstance(pres_asset.slide_content, list):
            for i, raw_slide in enumerate(pres_asset.slide_content, 1):
                title = raw_slide.get("title", f"Slide {i}")
                content = raw_slide.get("content", raw_slide.get("text", ""))
                notes = raw_slide.get("speaker_notes", None)

                # Cross-reference slide narration script if available
                raw_narr = None
                if script and hasattr(script, "script_content") and isinstance(script.script_content, dict):
                    slide_narrations = script.script_content.get("slide_narrations", {})
                    narr_item = slide_narrations.get(str(i)) or slide_narrations.get(i)
                    if narr_item and isinstance(narr_item, dict):
                        raw_narr = narr_item.get("narration")

                slides.append(SlideData(
                    slide_number=i,
                    title=title,
                    content=content,
                    speaker_notes=notes,
                    raw_narration=raw_narr
                ))

        # Default fallback slide if asset deck has no slides
        if not slides:
            slides = [
                SlideData(
                    slide_number=1,
                    title="Welcome to KONE Induction",
                    content="Welcome to your KONE onboarding session. We will cover company values, safety policies, and key HR contacts.",
                    raw_narration="Welcome to KONE. Today we begin your employee induction presentation."
                )
            ]

        session = PresentationSession(
            session_id=session_id,
            meeting_id=meeting.id if meeting else None,
            slides=slides,
            current_slide_index=0,
            total_slides=len(slides),
            presentation_state="WAITING"
        )
        logger.info(f"PresentationSessionService | Built PresentationSession for {session_id} with {len(slides)} slides.")
        return session

presentation_session_service = PresentationSessionService()
