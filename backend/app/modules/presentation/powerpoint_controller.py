import asyncio
import time
from pathlib import Path
from loguru import logger


class PowerPointController:
    def __init__(self):
        self.powerpoint = None
        self.presentation = None
        self.slide_show = None

    async def open(self, ppt_path: str, *, start_immediately: bool = False) -> None:
        """Open the presentation in PowerPoint and optionally start a windowed slideshow."""
        await self.open_slideshow(ppt_path, start_immediately=start_immediately)

    async def open_slideshow(self, ppt_path: str, *, start_immediately: bool = False) -> None:
        """
        Open PowerPoint presentation and optionally start a windowed slideshow once sharing is ready.
        """
        logger.info("PowerPointController | [PPT] Opening presentation")

        import pythoncom
        pythoncom.CoInitialize()

        import subprocess
        import win32com.client

        try:
            subprocess.run(["taskkill", "/f", "/im", "powerpnt.exe"], capture_output=True)
        except Exception:
            pass

        self.powerpoint = win32com.client.Dispatch("PowerPoint.Application")
        self.powerpoint.Visible = True

        try:
            self.powerpoint.WindowState = 2  # ppWindowMinimized
        except Exception as e:
            logger.warning(f"PowerPointController | Could not minimize PowerPoint window: {e}")

        abs_ppt = str(Path(ppt_path).resolve())
        self.presentation = self.powerpoint.Presentations.Open(
            abs_ppt,
            ReadOnly=True,
            WithWindow=True,
        )
        self.presentation.SlideShowSettings.ShowType = 2  # ppShowTypeWindow
        if start_immediately:
            self.presentation.SlideShowSettings.Run()
            self.slide_show = self.presentation.SlideShowWindow.View
            logger.info("PowerPointController | [PPT] Slideshow started in windowed mode")
        else:
            logger.info("PowerPointController | [PPT] Presentation loaded and waiting for slideshow start")

        await asyncio.sleep(1)

    async def start_slideshow(self) -> None:
        if not self.presentation:
            raise RuntimeError("PowerPoint presentation is not loaded")
        self.presentation.SlideShowSettings.Run()
        self.slide_show = self.presentation.SlideShowWindow.View
        logger.info("PowerPointController | [PPT] Slideshow started after sharing succeeded")
        await self.wait_for_slideshow_window(timeout=15)

    async def wait_for_slideshow_window(self, timeout: float = 15.0) -> bool:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            hwnd = self._find_slideshow_hwnd()
            if hwnd:
                logger.info(f"PowerPointController | [PPT] Found slideshow window: {hwnd}")
                return True
            await asyncio.sleep(0.5)
        logger.warning("PowerPointController | [PPT] Slideshow window not found; continuing without focus dependency")
        return False

    def _find_slideshow_hwnd(self):
        import win32gui

        hwnd = win32gui.FindWindow("screenClass", None)
        if hwnd:
            return hwnd

        hwnds = []

        def enum_cb(h, extra):
            title = win32gui.GetWindowText(h)
            if "PowerPoint Slide Show" in title:
                extra.append(h)
            return True

        win32gui.EnumWindows(enum_cb, hwnds)
        return hwnds[0] if hwnds else None

    async def focus_slideshow_window(self) -> None:
        """
        Attempt to surface the slideshow window without assuming prior focus.
        """
        hwnd = self._find_slideshow_hwnd()
        if not hwnd:
            logger.warning("PowerPointController | [PPT] Slideshow window not found; skipping focus update")
            return

        import win32con
        import win32gui

        try:
            win32gui.ShowWindow(hwnd, win32con.SW_SHOWNORMAL)
            win32gui.SetForegroundWindow(hwnd)
        except Exception as ex:
            logger.warning(f"PowerPointController | Failed to bring slideshow window to foreground: {ex}")

    async def recover_if_lost(self) -> None:
        logger.info("PowerPointController | [PPT] Recovering slideshow window")
        await self.wait_for_slideshow_window(timeout=10)

    def get_current_slide_index(self) -> int:
        """Return the 1-based index of the currently displayed slide in the slideshow."""
        if self.slide_show:
            try:
                return int(self.slide_show.CurrentShowPosition)
            except Exception as e:
                logger.debug(f"PowerPointController | Failed to query CurrentShowPosition: {e}")
        return 1

    def get_slide_media_shapes(self, slide_index: int) -> list:
        """Finds all media shapes on the requested slide."""
        media_shapes = []
        if not self.presentation:
            return media_shapes
        try:
            slide = self.presentation.Slides(slide_index)
            for shape in slide.Shapes:
                # Type 16 is msoMedia
                if shape.Type == 16:
                    media_shapes.append(shape)
        except Exception as e:
            logger.debug(f"PowerPointController | Could not inspect media shapes on slide {slide_index}: {e}")
        return media_shapes

    def play_media_on_slide(self, slide_index: int, shape_id: int = None) -> bool:
        """Starts or triggers playback for a media shape on the current slide."""
        if not self.slide_show:
            return False
        try:
            shapes = self.get_slide_media_shapes(slide_index)
            target_shape = None
            if shape_id is not None:
                for s in shapes:
                    if s.Id == shape_id:
                        target_shape = s
                        break
            elif shapes:
                target_shape = shapes[0]

            if target_shape:
                player = self.slide_show.Player(target_shape.Id)
                player.Play()
                logger.info(f"PowerPointController | Triggered Play() for media shape {target_shape.Id} on slide {slide_index}")
                return True
        except Exception as e:
            logger.warning(f"PowerPointController | Failed to trigger media play on slide {slide_index}: {e}")
        return False

    def is_media_playing_on_slide(self, slide_index: int) -> bool:
        """Queries if any media shape on the current slide is actively playing."""
        if not self.slide_show:
            return False
        try:
            shapes = self.get_slide_media_shapes(slide_index)
            for s in shapes:
                try:
                    player = self.slide_show.Player(s.Id)
                    # player.State: 0 = ppPlaying, 1 = ppPaused, 2 = ppStopped (or 3 in some Office editions)
                    if player.State == 0:
                        return True
                except Exception:
                    pass
        except Exception as e:
            logger.debug(f"PowerPointController | Media playing query notice: {e}")
        return False

    async def next_slide(self) -> None:
        """
        Navigate to next slide in show.
        """
        if self.slide_show:
            try:
                self.slide_show.Next()
                logger.info("PowerPointController | Advanced to next slide.")
            except Exception as e:
                logger.error(f"PowerPointController | Slide advance failed: {e}")

    async def prev_slide(self) -> None:
        """
        Navigate to previous slide in show.
        """
        if self.slide_show:
            try:
                self.slide_show.Previous()
                logger.info("PowerPointController | Reverted to previous slide.")
            except Exception as e:
                logger.error(f"PowerPointController | Slide revert failed: {e}")

    async def close(self) -> None:
        """Close the presentation and quit the PowerPoint application COM instance."""
        await self.close_presentation()

    async def stop(self) -> None:
        """Stop the current slideshow and close the window cleanly."""
        await self.close_presentation()

    async def close_presentation(self) -> None:
        """
        Close the presentation and quit the PowerPoint application COM instance.
        """
        import pythoncom
        pythoncom.CoInitialize()
        try:
            if self.presentation:
                self.presentation.Close()
                self.presentation = None
            if self.powerpoint:
                self.powerpoint.Quit()
                self.powerpoint = None
            logger.info("PowerPointController | PowerPoint presentation closed successfully.")
        except Exception as e:
            logger.warning(f"PowerPointController | PowerPoint close failed: {e}")
        finally:
            import gc

            gc.collect()
