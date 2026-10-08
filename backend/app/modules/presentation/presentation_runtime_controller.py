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
        self.presentation_state = "READY"
        self.share_successful = False  # tracks if Teams sharing succeeded
    def _transition_state(self, state: str) -> None:
        if self.presentation_state != state:
            logger.info(f"PresentationRuntimeController | [STATE] {self.presentation_state} -> {state}")
            self.presentation_state = state

    async def run(self) -> None:
        if not self.teams_page:
            raise RuntimeError("Teams page is not available")

        session_dir = storage_service.get_session_dir(self.session_id)
        manifest_path = session_dir / "manifest.json"
        if not manifest_path.exists():
            raise FileNotFoundError(f"Presentation manifest not found: {manifest_path}")

        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        from app.modules.presentation.powerpoint_controller import PowerPointController

        self.ppt_controller = PowerPointController()
        logger.info("PresentationRuntimeController | [PPT] Opening presentation")
        
        ppt_path = session_dir / manifest["presentation"]
        if not ppt_path.exists():
            # Try within presentation/ subfolder (standard structured mode)
            ppt_path = session_dir / "presentation" / manifest["presentation"]
            
        await self.ppt_controller.open(str(ppt_path), start_immediately=True)
        self._transition_state("EDITOR_OPEN")
        logger.info("PresentationRuntimeController | [PPT] Presentation editor and slideshow ready")

        logger.info("PresentationRuntimeController | [SHARE] Opening share flow")
        share_succeeded = await self._share_with_retry(
            lambda page: self._share_presentation_window(page),
            self.teams_page,
        )
        if share_succeeded:
            self.share_successful = True
            self._transition_state("SLIDESHOW_RUNNING")
        else:
            logger.error("PresentationRuntimeController | Sharing failed, keeping PowerPoint open for manual intervention")
            self.share_successful = False
            raise RuntimeError("Teams sharing confirmation was not detected")

        logger.info("PresentationRuntimeController | [PRESENTATION] Starting narration")
        audio = get_audio_controller(self.session_id)
        if not audio.validate_audio_route():
            raise RuntimeError("Audio route validation failed before narration playback")
        
        audio_file = manifest.get("audio", "narration.wav")
        audio_path = session_dir / audio_file
        if not audio_path.exists():
            audio_path = session_dir / "audio" / audio_file
        if not audio_path.exists():
            audio_path = storage_service.get_generated_audio_dir(self.session_id) / audio_file

        audio.play_narration(audio_path, manifest.get("duration_ms"))

        from app.modules.presentation.timeline_executor import TimelineExecutor

        # Load slide metadata for media timing coordination if present
        slides_metadata = []
        slides_meta_path = session_dir / "slides_metadata.json"
        if slides_meta_path.exists():
            try:
                with open(slides_meta_path, "r", encoding="utf-8") as smf:
                    slides_metadata = json.load(smf)
            except Exception as sm_err:
                logger.warning(f"PresentationRuntimeController | Could not read slides_metadata.json: {sm_err}")

        # Map slide number to video info
        slide_videos = {}
        for s in slides_metadata:
            s_num = s.get("slide_number")
            v_meta = s.get("video_metadata", [])
            if s_num and v_meta:
                slide_videos[s_num] = v_meta

        executor = TimelineExecutor(str(session_dir / manifest["timeline"]))
        current_visible_slide = 1
        slide_start_monotonic = {}
        slide_start_monotonic[1] = asyncio.get_running_loop().time()

        def is_slide_media_busy(slide_num: int) -> bool:
            """
            Checks if slide_num has an embedded video that is currently playing or has not
            met its required playback duration.
            """
            if not self.ppt_controller:
                return False

            # Check COM player state directly
            if self.ppt_controller.is_media_playing_on_slide(slide_num):
                return True

            # If slide has video metadata with known duration, check elapsed time on slide
            if slide_num in slide_videos:
                for v in slide_videos[slide_num]:
                    dur = v.get("duration")
                    if dur and dur > 0:
                        start_t = slide_start_monotonic.get(slide_num)
                        if start_t:
                            elapsed = asyncio.get_running_loop().time() - start_t
                            if elapsed < dur:
                                return True
            return False

        def get_current_slide() -> int:
            if self.ppt_controller:
                return self.ppt_controller.get_current_slide_index()
            return current_visible_slide

        async def handle_goto_slide(slide_num: int):
            nonlocal current_visible_slide
            logger.info(f"PresentationRuntimeController | Event trigger: goto_slide {slide_num} (current slide: {current_visible_slide})")
            while current_visible_slide < slide_num:
                await self.ppt_controller.next_slide()
                current_visible_slide += 1
                slide_start_monotonic[current_visible_slide] = asyncio.get_running_loop().time()
                await asyncio.sleep(0.5)
            while current_visible_slide > slide_num:
                await self.ppt_controller.prev_slide()
                current_visible_slide -= 1
                slide_start_monotonic[current_visible_slide] = asyncio.get_running_loop().time()
                await asyncio.sleep(0.5)

            # Check if entering slide with video and trigger play if needed
            if current_visible_slide in slide_videos:
                v_list = slide_videos[current_visible_slide]
                for v in v_list:
                    if not v.get("supported", True):
                        logger.warning(
                            f"PresentationRuntimeController | Notice on slide {current_visible_slide}: "
                            f"{v.get('reason')}"
                        )
                    # Trigger play for safety if not already auto-playing
                    self.ppt_controller.play_media_on_slide(current_visible_slide, v.get("shape_id"))

        try:
            await asyncio.sleep(1)
            await executor.execute(
                audio_controller=audio,
                on_goto_slide=handle_goto_slide,
                is_slide_busy=is_slide_media_busy,
                get_current_slide=get_current_slide,
            )
            
            # Wait for narration audio playback to fully complete before exiting
            logger.info("PresentationRuntimeController | Timeline finished. Waiting for remaining narration audio playback to complete...")
            while audio.playing:
                await asyncio.sleep(0.2)
                
            logger.info("PresentationRuntimeController | Timeline and narration audio execution completed successfully.")
            self._transition_state("FINISHED")
        finally:
            try:
                await teams_controller.stop_sharing(self.teams_page)
            except Exception:
                pass
            # Close PowerPoint only if sharing succeeded; otherwise keep it open for user
            if self.share_successful:
                try:
                    await self._close_powerpoint()
                except Exception:
                    pass
            try:
                from app.modules.meeting_bot.media.audio_controller import cleanup_audio_controller

                cleanup_audio_controller(self.session_id)
            except Exception as e:
                logger.warning(f"PresentationRuntimeController | Audio preloader cleanup failed: {e}")

    async def _share_with_retry(self, share_action, page: Optional[Page], *, max_attempts: int = 2) -> bool:
        last_error: Optional[Exception] = None
        for attempt in range(1, max_attempts + 1):
            try:
                if attempt > 1:
                    logger.warning(f"PresentationRuntimeController | [SHARE] Retry attempt {attempt}/{max_attempts}")
                    await self._reset_share_flow(page)
                result = await share_action(page)
                await self._wait_for_sharing_confirmed(page)
                return bool(result)
            except Exception as exc:
                last_error = exc
                logger.warning(f"PresentationRuntimeController | [SHARE] Share attempt {attempt}/{max_attempts} failed: {exc}")
                if attempt >= max_attempts:
                    break

        if last_error is not None:
            raise last_error
        return False

    async def _share_presentation_window(self, page: Optional[Page]) -> bool:
        t_controller = self._get_teams_controller()
        native_share = self._get_native_share_controller()
        verification = self._get_share_verification_controller()

        await t_controller.open_share_panel(page)
        await native_share.activate_picker()
        await native_share.click_window_tab()
        ppt_name = Path(self.ppt_path).name
        await native_share.select_window("PowerPoint Slide Show", presentation_name=ppt_name)
        await native_share.click_share()
        
        return await verification.wait_for_share_confirmation(page, timeout=10.0)

    def _get_teams_controller(self):
        return teams_controller

    def _get_native_share_controller(self):
        from app.modules.presentation.native_share_controller import NativeShareController

        return NativeShareController()

    def _get_share_verification_controller(self):
        from app.modules.presentation.share_verification_controller import ShareVerificationController

        return ShareVerificationController()

    async def _reset_share_flow(self, page: Optional[Page]) -> None:
        if page is None or page.is_closed():
            return
        logger.info("PresentationRuntimeController | [SHARE] Resetting share flow")
        try:
            await teams_controller.stop_sharing(page)
        except Exception:
            pass
        try:
            await page.keyboard.press("Escape")
        except Exception:
            pass
        await asyncio.sleep(0.5)

    async def _wait_for_sharing_confirmed(self, page: Optional[Page], *, timeout: float = 10.0) -> None:
        if page is None or page.is_closed():
            raise RuntimeError("Teams page is not available for sharing verification")

        logger.info("PresentationRuntimeController | [SHARE] Waiting for Teams sharing confirmation")
        verification_controller = self._get_share_verification_controller()
        await verification_controller.wait_for_share_confirmation(page, timeout=timeout)

    async def _close_powerpoint(self) -> None:
        if self.ppt_controller:
            await self.ppt_controller.close()
            self.ppt_controller = None
