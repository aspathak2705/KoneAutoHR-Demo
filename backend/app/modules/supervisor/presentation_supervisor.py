from loguru import logger
from sqlalchemy.orm import Session as DBSession
from app.modules.presentation.presentation_engine import PresentationEngine
from app.modules.presentation.slide_controller import SlideController
from app.modules.presentation.video_controller import VideoController
from app.modules.presentation.timing_controller import TimingController
from app.modules.presentation.verification_engine import VerificationEngine
from app.modules.browser.browser_agent import BrowserAgent
from app.modules.presentation.session_events import session_events

class PresentationSupervisor:
    """
    Module 4 — Presentation Supervisor
    Supervises PresentationEngine (slides, timing, verification) and BrowserAgent (joining, sharing, recovery).
    Coordinates actions for clean meeting execution.
    """
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.engine = PresentationEngine(session_id)
        self.slide_ctrl = SlideController(session_id)
        self.video_ctrl = VideoController(session_id)
        self.timing_ctrl = TimingController(session_id)
        self.verify_engine = VerificationEngine(session_id)
        self.browser_agent = BrowserAgent()

    async def initialize_and_join(self, db: DBSession, teams_url: str, asset_id: str, guest_name: str) -> bool:
        logger.info(f"PresentationSupervisor | Initializing session: {self.session_id}")
        
        # 1. Load Presentation Asset
        loaded = await self.engine.load_presentation(db, asset_id)
        if not loaded:
            logger.error("PresentationSupervisor | Failed to load presentation asset.")
            session_events.publish(self.session_id, "AssetMissing", {"asset_id": asset_id})
            return False
        session_events.publish(self.session_id, "AssetLoaded", {"asset_id": asset_id})

        # 2. Launch Browser Agent
        launch_res = await self.browser_agent.launch()
        if not launch_res.get("ready"):
            logger.error("PresentationSupervisor | Failed to launch browser agent.")
            return False

        # 3. Navigate & Join Teams Call
        await self.browser_agent.navigate(teams_url)
        await self.browser_agent.join_guest(guest_name)
        
        # 4. Verify Connection
        connected = await self.browser_agent.verify_connected()
        if connected:
            session_events.publish(self.session_id, "MeetingJoined", {"session_id": self.session_id})
            # Launch local PowerPoint slideshow
            await self.engine.start_slideshow()
            session_events.publish(self.session_id, "PresentationLoaded")
            return True
        
        return False

    async def present_slide(self, slide_number: int, narration_before: list, narration_during: list, narration_after: list, expected_duration: int = 15) -> None:
        logger.info(f"PresentationSupervisor | Presenting slide {slide_number}...")
        
        # Verify PowerPoint focus and window active state
        await self.verify_engine.verify_powerpoint_focus()
        
        # Navigate to Slide
        await self.slide_ctrl.go_to_slide(slide_number)
        await self.verify_engine.verify_slide_number(slide_number)
        session_events.publish(self.session_id, "SlideVerified", {"slide_number": slide_number})

        # Process timing delay based on speech lengths
        await self.timing_ctrl.wait_for_transition(expected_duration)

    async def play_embedded_video(self, asset_url: str, duration: int) -> None:
        logger.info(f"PresentationSupervisor | Triggering embedded video play: {asset_url}")
        session_events.publish(self.session_id, "VideoStarted", {"asset_url": asset_url})
        await self.video_ctrl.play_video(asset_url)
        await self.video_ctrl.wait_until_finished(duration)
        session_events.publish(self.session_id, "VideoFinished", {"asset_url": asset_url})

    async def shutdown(self) -> None:
        logger.info("PresentationSupervisor | Shutting down supervisor session components...")
        await self.engine.stop_slideshow()
        await self.browser_agent.leave_meeting()
