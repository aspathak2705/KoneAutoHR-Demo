import asyncio
from typing import Dict, Any, Optional, List
from loguru import logger

from app.modules.presentation.session_script_models import ScriptStep
from app.modules.presentation.speech_engine import speech_engine
from app.modules.presentation.models import NarrationBlock
from app.modules.presentation.presentation_controller import PresentationController
from app.services.attendance_service import attendance_service
from app.services.teams_runtime_service import teams_runtime_service

# Gap 6 Internal Component Helpers
class SlideController:
    async def display_and_verify(self, controller: PresentationController, slide_num: int) -> bool:
        await controller.show_slide(slide_num)
        return await controller.verify_slide(slide_num)

class SpeechController:
    async def speak_sentences(self, sentences: List[str], slide_num: int = 0) -> None:
        if not sentences:
            return
        text = " ".join(sentences)
        words = len(text.split())
        duration = max(2.5, round(words / 2.5, 1))
        await speech_engine.speak(NarrationBlock(
            slide_number=slide_num,
            text=text,
            estimated_duration=duration
        ))

class ProgressTracker:
    def record_progress(self, session_id: str, slide_num: int) -> None:
        logger.info(f"ProgressTracker | Session {session_id} progressed to slide {slide_num}")

class WaitForParticipantsHandler:
    """Evaluates attendee threshold OR timeout using AttendanceService with periodic fallback announcements."""
    async def execute(self, step: ScriptStep, session_id: str) -> None:
        rule = step.completion
        timeout = rule.timeout_seconds if rule and rule.timeout_seconds else 60
        logger.info(f"Handler | [WAIT_FOR_PARTICIPANTS] Waiting for participants (timeout: {timeout}s)")
        
        elapsed = 0
        periodic_idx = 0
        periodic_speeches = step.fallback.periodic_speeches if (step.fallback and step.fallback.periodic_speeches) else []

        while elapsed < timeout:
            attendees = attendance_service.get_attendance(session_id)
            ready_count = len(attendees.get("attendees", [])) if isinstance(attendees, dict) else 0
            if ready_count >= 1:
                logger.info(f"Handler | [WAIT_FOR_PARTICIPANTS] Attendees joined ({ready_count}). Proceeding.")
                return
            
            # Gap 4: Periodic spoken waiting announcements every 20 seconds
            if elapsed > 0 and elapsed % 20 == 0 and periodic_speeches:
                speech_text = periodic_speeches[periodic_idx % len(periodic_speeches)]
                logger.info(f"Handler | [WAIT_FOR_PARTICIPANTS] Periodic waiting announcement: '{speech_text}'")
                await speech_engine.speak(NarrationBlock(slide_number=0, text=speech_text, estimated_duration=3.5))
                periodic_idx += 1

            await asyncio.sleep(2)
            elapsed += 2

class SpokenTextHandler:
    """Delivers pre-generated sentence arrays for GREETING, INTRODUCTION, AUDIO_CHECK, SESSION_RULES, ICE_BREAKER, UNDERSTANDING_CHECK, SUMMARY."""
    def __init__(self, step_type_name: str):
        self.step_type_name = step_type_name
        self.speech_ctrl = SpeechController()

    async def execute(self, step: ScriptStep, session_id: str) -> None:
        sentences = step.speech or [f"Executing {self.step_type_name} step."]
        logger.info(f"Handler | [{self.step_type_name}] Delivering {len(sentences)} pre-generated sentences...")
        await self.speech_ctrl.speak_sentences(sentences, slide_num=step.slide_number or 0)

class PresentationHandler:
    """
    Gap 6 — Composed PresentationHandler
    Delegates to SlideController, SpeechController, and ProgressTracker internally.
    """
    def __init__(self):
        self.slide_ctrl = SlideController()
        self.speech_ctrl = SpeechController()
        self.tracker = ProgressTracker()

    async def execute(self, step: ScriptStep, session_id: str, controller: PresentationController) -> None:
        slide_num = step.slide_number or 1
        logger.info(f"Handler | [PresentationHandler] Processing slide_id '{step.slide_id}' (Slide {slide_num})")

        # 1. Speak 'before' sentences
        if step.before:
            await self.speech_ctrl.speak_sentences(step.before, slide_num=slide_num)

        # 2. Advance & verify slide via SlideController
        await self.slide_ctrl.display_and_verify(controller, slide_num)
        self.tracker.record_progress(session_id, slide_num)

        # 3. Speak 'during' sentences
        if step.during:
            await self.speech_ctrl.speak_sentences(step.during, slide_num=slide_num)
        elif step.speech:
            await self.speech_ctrl.speak_sentences(step.speech, slide_num=slide_num)

        # 4. Speak 'after' sentences
        if step.after:
            await self.speech_ctrl.speak_sentences(step.after, slide_num=slide_num)

# Gap 7 Future Action Handlers
class PlayVideoHandler:
    async def execute(self, step: ScriptStep, session_id: str) -> None:
        logger.info(f"Handler | [PLAY_VIDEO] Playing asset: {step.asset_url}")
        await asyncio.sleep(2)

class ShowImageHandler:
    async def execute(self, step: ScriptStep, session_id: str) -> None:
        logger.info(f"Handler | [SHOW_IMAGE] Displaying image asset: {step.asset_url}")
        await asyncio.sleep(2)

class PollHandler:
    async def execute(self, step: ScriptStep, session_id: str) -> None:
        logger.info(f"Handler | [POLL] Launching interactive poll...")
        await asyncio.sleep(2)

class WaitForQuestionsHandler:
    """Pauses interpreter and transfers control to Phase 2B.2 Live Q&A."""
    def __init__(self):
        self.speech_ctrl = SpeechController()

    async def execute(self, step: ScriptStep, session_id: str) -> None:
        sentences = step.speech or ["Opening the floor for live employee Q&A."]
        logger.info(f"Handler | [WAIT_FOR_QUESTIONS] {sentences}")
        await speech_engine.speak(NarrationBlock(slide_number=99, text=" ".join(sentences), estimated_duration=3.5))

class ClosingHandler:
    """Delivers final closing thank-you and leaves meeting."""
    async def execute(self, step: ScriptStep, session_id: str) -> None:
        sentences = step.speech or ["Thank you all for participating in today's induction session!"]
        logger.info(f"Handler | [CLOSING] {sentences}")
        await speech_engine.speak(NarrationBlock(slide_number=100, text=" ".join(sentences), estimated_duration=3.5))
        logger.info(f"Handler | [CLOSING] Calling teams_runtime_service.leave_meeting() for {session_id}...")
        teams_runtime_service.leave_meeting(session_id)
