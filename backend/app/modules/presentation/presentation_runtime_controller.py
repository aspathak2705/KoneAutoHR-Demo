import asyncio
import json
from pathlib import Path
from typing import Any, Dict, Optional

from loguru import logger
from playwright.async_api import Page

from app.modules.meeting_bot.media.audio_controller import get_audio_controller
from app.modules.meeting_bot.teams.teams_controller import teams_controller
from app.services.storage_service import storage_service


class PresentationRuntimeController:
    """
    Deterministic owner of the PowerPoint presentation lifecycle.
    Loads manifest.json and delegates playback to AudioController and TimelineExecutor.
    """

    def __init__(self, session_id: str, ppt_path: str, teams_page: Optional[Page]):
        self.session_id = session_id
        self.ppt_path = ppt_path
        self.teams_page = teams_page
        self.ppt_controller = None

    async def run(self) -> None:
        if not self.teams_page:
            raise RuntimeError("Teams page is not available")

        # 1. Load manifest.json (Phase 3 spec)
        session_dir = storage_service.get_session_dir(self.session_id)
        manifest_path = session_dir / "manifest.json"
        if not manifest_path.exists():
            raise FileNotFoundError(f"Presentation manifest not found: {manifest_path}")
            
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        # 2. Open PPT and start slideshow
        from app.modules.presentation.powerpoint_controller import PowerPointController
        self.ppt_controller = PowerPointController()
        await self.ppt_controller.open_slideshow(str(session_dir / manifest["presentation"]))

        # 3. Share PowerPoint window
        await teams_controller.share_powerpoint(self.teams_page)
        
        # Wait for sharing indicator to confirm active presentation stream
        logger.info("PresentationRuntimeController | Waiting for Teams active sharing indicator...")
        sharing_active = False
        for timeout in range(15):
            for sel in ["button[data-tid='stop-presenting-button']", "button[aria-label*='Stop sharing' i]", "button:has-text('Stop sharing')"]:
                try:
                    if await self.teams_page.locator(sel).is_visible():
                        sharing_active = True
                        break
                except Exception:
                    pass
            if sharing_active:
                break
            await asyncio.sleep(1)
        
        if sharing_active:
            logger.info("PresentationRuntimeController | Teams sharing stream is active. Waiting 5 additional seconds for stream visibility...")
            await asyncio.sleep(5)
        else:
            logger.warning("PresentationRuntimeController | Sharing indicator not detected. Proceeding anyway with a 5-second default buffer.")
            await asyncio.sleep(5)

        # 4. Play narration.wav
        audio = get_audio_controller(self.session_id)
        audio.play_narration(session_dir / manifest["audio"])

        # 5. Execute timeline events
        from app.modules.presentation.timeline_executor import TimelineExecutor
        executor = TimelineExecutor(str(session_dir / manifest["timeline"]))

        current_visible_slide = 1

        async def handle_goto_slide(slide_num: int):
            nonlocal current_visible_slide
            logger.info(f"PresentationRuntimeController | Event trigger: goto_slide {slide_num} (current slide: {current_visible_slide})")
            while current_visible_slide < slide_num:
                await self.ppt_controller.next_slide()
                current_visible_slide += 1
                await asyncio.sleep(0.5)
            while current_visible_slide > slide_num:
                await self.ppt_controller.prev_slide()
                current_visible_slide -= 1
                await asyncio.sleep(0.5)

        try:
            # Wait for audio to start playing and buffer
            await asyncio.sleep(1)
            await executor.execute(audio, handle_goto_slide)
            logger.info("PresentationRuntimeController | Timeline execution completed successfully.")
        finally:
            try:
                await teams_controller.stop_sharing(self.teams_page)
            except Exception:
                pass
            try:
                await self._close_powerpoint()
            except Exception:
                pass
            try:
                from app.modules.meeting_bot.media.audio_controller import cleanup_audio_controller
                cleanup_audio_controller(self.session_id)
            except Exception as e:
                logger.warning(f"PresentationRuntimeController | Audio preloader cleanup failed: {e}")

    async def _close_powerpoint(self) -> None:
        if self.ppt_controller:
            await self.ppt_controller.close_presentation()
            self.ppt_controller = None
