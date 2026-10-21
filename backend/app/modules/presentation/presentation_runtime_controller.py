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
        if not ppt_path.exists():
            ppt_path = session_dir / "presentation.pptx"
        if not ppt_path.exists():
            # Fallback: check session presentation model and decrypt to session_dir
            try:
                from app.db.database import SessionLocal
                from app.models.session import Session
                from app.core.security.secure_storage import secure_storage
                import shutil
                with SessionLocal() as db:
                    sess = db.query(Session).filter(Session.id == self.session_id).first()
                    if sess and sess.presentation:
                        with secure_storage.open_decrypted_file(sess.presentation) as dec_p:
                            fallback_path = session_dir / manifest["presentation"]
                            shutil.copy2(dec_p, fallback_path)
                            ppt_path = fallback_path
            except Exception as e:
                logger.warning(f"PresentationRuntimeController | Failed to fallback-copy presentation: {e}")
            
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

        # Map slide number to video info (load from slides_metadata.json or dynamically inspect presentation)
        slide_videos = {}
        for s in slides_metadata:
            s_num = s.get("slide_number")
            v_meta = s.get("video_metadata", [])
            if s_num and v_meta:
                slide_videos[s_num] = v_meta

        # Fallback: scan media shapes directly from presentation COM if slides_metadata is absent or lacks entries
        if not slide_videos and self.ppt_controller and self.ppt_controller.presentation:
            try:
                pres_com = self.ppt_controller.presentation
                for s_idx in range(1, pres_com.Slides.Count + 1):
                    shapes = self.ppt_controller.get_slide_media_shapes(s_idx)
                    if shapes:
                        v_list = []
                        for shp in shapes:
                            dur = 0.0
                            try:
                                if hasattr(shp, "MediaFormat") and shp.MediaFormat.Length > 0:
                                    dur = shp.MediaFormat.Length / 1000.0
                            except Exception:
                                pass
                            v_list.append({
                                "shape_id": shp.Id,
                                "shape_name": shp.Name,
                                "duration": dur,
                                "supported": True
                            })
                        slide_videos[s_idx] = v_list
                if slide_videos:
                    logger.info(f"PresentationRuntimeController | Dynamically discovered media on slides: {list(slide_videos.keys())}")
            except Exception as dyn_err:
                logger.debug(f"PresentationRuntimeController | Dynamic media scan notice: {dyn_err}")

        executor = TimelineExecutor(str(session_dir / manifest["timeline"]))
        current_visible_slide = 1
        slide_start_monotonic = {}
        slide_start_monotonic[1] = asyncio.get_running_loop().time()

        # Map slide number to narration window (start_ms, end_ms) based on timeline / manifest
        slide_narration_bounds = {}
        events_list = sorted(executor.events, key=lambda x: x.get("time_ms", 0))
        for i, ev in enumerate(events_list):
            s_num = ev.get("slide")
            st_ms = float(ev.get("time_ms", 0))
            s_audio_meta = manifest.get("slide_audio_metadata", {}).get(str(s_num), {})
            dur_ms = s_audio_meta.get("duration_ms")
            if dur_ms is not None and dur_ms > 0:
                end_ms = st_ms + float(dur_ms)
            elif i + 1 < len(events_list):
                end_ms = float(events_list[i + 1].get("time_ms", 0))
            else:
                end_ms = float(manifest.get("duration_ms", st_ms))
            slide_narration_bounds[s_num] = (st_ms, end_ms)

        slide_video_started = set()
        slide_video_finished = set()

        def is_slide_media_busy(slide_num: int) -> bool:
            """
            Checks if slide_num has an embedded video that is currently playing or has not
            met its required playback duration.
            """
            if not self.ppt_controller:
                return False

            if slide_num not in slide_videos:
                return False

            # If video has finished completely, slide is no longer busy
            if slide_num in slide_video_finished:
                return False

            # If video was started, check if it's still playing or within its duration
            if slide_num in slide_video_started:
                if self.ppt_controller.is_media_playing_on_slide(slide_num):
                    return True
                for v in slide_videos[slide_num]:
                    dur = v.get("duration")
                    if dur and dur > 0:
                        start_t = slide_start_monotonic.get(f"{slide_num}_video")
                        if start_t:
                            elapsed = asyncio.get_running_loop().time() - start_t
                            if elapsed < dur:
                                return True
                slide_video_finished.add(slide_num)
                return False

            # Video hasn't started yet: slide is busy waiting for video to play
            return True

        def get_current_slide() -> int:
            if self.ppt_controller:
                return self.ppt_controller.get_current_slide_index()
            return current_visible_slide

        async def check_and_play_slide_video(slide_num: int):
            """
            Starts the embedded video on slide_num ONLY AFTER the slide's narration has finished.
            """
            if slide_num not in slide_videos or slide_num in slide_video_started:
                return

            bounds = slide_narration_bounds.get(slide_num)
            has_narration = False
            if bounds:
                st_ms, end_ms = bounds
                s_meta = manifest.get("slide_audio_metadata", {}).get(str(slide_num), {})
                if s_meta.get("type") != "SILENT" and (end_ms - st_ms) > 100:
                    has_narration = True

            # If slide has narration, wait until current playback position reaches or exceeds end_ms
            if has_narration and bounds:
                _, end_ms = bounds
                while audio.playing and audio.position() < (end_ms - 50):
                    await asyncio.sleep(0.1)

            if slide_num in slide_video_started:
                return

            slide_video_started.add(slide_num)
            slide_start_monotonic[f"{slide_num}_video"] = asyncio.get_running_loop().time()
            logger.info(f"PresentationRuntimeController | Narration finished for slide {slide_num}. Starting embedded video playback now.")

            v_list = slide_videos.get(slide_num, [])
            for v in v_list:
                if not v.get("supported", True):
                    logger.warning(
                        f"PresentationRuntimeController | Notice on slide {slide_num}: {v.get('reason')}"
                    )
                self.ppt_controller.play_media_on_slide(slide_num, v.get("shape_id"))

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

            # Check if entering slide with video and launch sequencing task
            if current_visible_slide in slide_videos:
                asyncio.create_task(check_and_play_slide_video(current_visible_slide))

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
