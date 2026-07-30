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
    Audio completion drives slide advancement. No slide detection.
    """

    def __init__(self, session_id: str, ppt_path: str, teams_page: Optional[Page]):
        self.session_id = session_id
        self.ppt_path = ppt_path
        self.teams_page = teams_page
        self.powerpoint = None
        self.presentation = None
        self.slide_show = None

    async def run(self) -> None:
        if not self.teams_page:
            raise RuntimeError("Teams page is not available")
        if not self.ppt_path:
            raise RuntimeError("PowerPoint file path is not available")

        manifest = self._load_manifest()
        audio = get_audio_controller(self.session_id)
        audio.preload_all_tracks()

        await self._launch_powerpoint_windowed()
        await teams_controller.share_presentation_window(self.teams_page, "PowerPoint Slide Show")
        
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
            logger.info("PresentationRuntimeController | Teams sharing stream is active. Waiting 4 additional seconds for video decoding...")
            await asyncio.sleep(4)
        else:
            logger.warning("PresentationRuntimeController | Sharing indicator not detected. Proceeding anyway with a 5-second default buffer.")
            await asyncio.sleep(5)

        current_visible_slide = 1

        try:
            for idx, track in enumerate(manifest["tracks"]):
                filename = track["filename"]
                slide_num = track.get("slide_number", 0)
                label = track.get("label", "")
                
                # Welcomes/greetings (slide_number 0) run on slide 1
                target_slide = max(1, slide_num)
                if slide_num == 99:
                    target_slide = current_visible_slide
                
                # Progress slides dynamically to align with narration target
                while current_visible_slide < target_slide:
                    logger.info(f"PresentationRuntimeController | Advancing slide to: {current_visible_slide + 1} for track: {label}")
                    await self._next_slide()
                    current_visible_slide += 1
                    await asyncio.sleep(1) # transition pause
                
                if idx > 0:
                    logger.info("PresentationRuntimeController | Pause of 2 seconds between slide narrations...")
                    await asyncio.sleep(2)

                logger.info(f"PresentationRuntimeController | Playing track: {filename} ({label}) on Slide {current_visible_slide}")
                await audio.play_and_wait(filename)
                
            logger.info("PresentationRuntimeController | Presentation timeline completed.")
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

    def _load_manifest(self) -> Dict[str, Any]:
        session_dir = storage_service.get_session_dir(self.session_id)
        manifest_path = session_dir / "audio_manifest.json"
        
        if not manifest_path.exists():
            # Fallback to presentation.json conversion
            presentation_path = session_dir / "presentation_assets" / "presentation.json"
            if presentation_path.exists():
                with open(presentation_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                tracks = []
                for s in data.get("slides", []):
                    tracks.append({
                        "label": f"slide_{s['number']}",
                        "slide_number": s["number"],
                        "filename": s["audio"]
                    })
                return {"session_id": self.session_id, "tracks": tracks}
            # Fallback to direct directory scan
            return self._build_manifest_from_audio()

        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
        return manifest

    def _build_manifest_from_audio(self) -> Dict[str, Any]:
        audio_dir = storage_service.get_session_dir(self.session_id) / "audio"
        audio = get_audio_controller(self.session_id)
        tracks = []

        # Sort dynamically: slide_X, intro, greeting etc.
        raw_files = sorted(audio_dir.glob("*.mp3"))
        for audio_file in raw_files:
            stem = audio_file.stem
            slide_num = 0
            if "slide_" in stem:
                parts = stem.split("_")
                if len(parts) >= 2 and parts[1].isdigit():
                    slide_num = int(parts[1])
            elif "closing" in stem:
                slide_num = 99
            
            tracks.append({
                "label": stem,
                "slide_number": slide_num,
                "filename": audio_file.name
            })

        manifest = {
            "session_id": self.session_id,
            "tracks": tracks
        }
        return manifest

    async def _launch_powerpoint_windowed(self) -> None:
        def start() -> None:
            import pythoncom
            import win32com.client
            import subprocess

            # Kill existing PowerPoint instances to avoid locks/read-only prompts
            try:
                subprocess.run(["taskkill", "/f", "/im", "powerpnt.exe"], capture_output=True)
            except Exception:
                pass

            pythoncom.CoInitialize()
            self.powerpoint = win32com.client.Dispatch("PowerPoint.Application")
            self.powerpoint.Visible = True
            
            # Minimize the main PowerPoint window so only the slideshow is prominent
            try:
                self.powerpoint.WindowState = 2  # ppWindowMinimized
            except Exception as e:
                logger.warning(f"PresentationRuntimeController | Could not minimize PowerPoint window: {e}")

            self.presentation = self.powerpoint.Presentations.Open(
                str(Path(self.ppt_path).resolve()),
                ReadOnly=True,
                WithWindow=True,
            )
            self.presentation.SlideShowSettings.ShowType = 2
            self.presentation.SlideShowSettings.Run()
            self.slide_show = self.presentation.SlideShowWindow.View

        await asyncio.to_thread(start)
        await asyncio.sleep(3)
        logger.info("PresentationRuntimeController | PowerPoint windowed slide show started.")

    async def _next_slide(self) -> None:
        def advance() -> None:
            if self.slide_show:
                self.slide_show.Next()

        await asyncio.to_thread(advance)
        await asyncio.sleep(0.2)

    async def _close_powerpoint(self) -> None:
        def close() -> None:
            try:
                if self.presentation:
                    self.presentation.Close()
                if self.powerpoint:
                    self.powerpoint.Quit()
            except Exception as e:
                logger.warning(f"PresentationRuntimeController | PowerPoint close failed: {e}")

        await asyncio.to_thread(close)
