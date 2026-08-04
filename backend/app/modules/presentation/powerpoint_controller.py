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

        def start() -> None:
            import pythoncom
            import subprocess
            import win32com.client

            try:
                subprocess.run(["taskkill", "/f", "/im", "powerpnt.exe"], capture_output=True)
            except Exception:
                pass

            pythoncom.CoInitialize()
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

        await asyncio.to_thread(start)
        await asyncio.sleep(1)

    async def start_slideshow(self) -> None:
        def run_show() -> None:
            if not self.presentation:
                raise RuntimeError("PowerPoint presentation is not loaded")
            self.presentation.SlideShowSettings.Run()
            self.slide_show = self.presentation.SlideShowWindow.View
            logger.info("PowerPointController | [PPT] Slideshow started after sharing succeeded")

        await asyncio.to_thread(run_show)
        await self.wait_for_slideshow_window(timeout=15)

    async def wait_for_slideshow_window(self, timeout: float = 15.0) -> bool:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            hwnd = await asyncio.to_thread(self._find_slideshow_hwnd)
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
        hwnd = await asyncio.to_thread(self._find_slideshow_hwnd)
        if not hwnd:
            logger.warning("PowerPointController | [PPT] Slideshow window not found; skipping focus update")
            return

        def activate() -> None:
            import win32con
            import win32gui

            try:
                win32gui.ShowWindow(hwnd, win32con.SW_SHOWNORMAL)
                win32gui.SetForegroundWindow(hwnd)
            except Exception as ex:
                logger.warning(f"PowerPointController | Failed to bring slideshow window to foreground: {ex}")

        await asyncio.to_thread(activate)

    async def recover_if_lost(self) -> None:
        logger.info("PowerPointController | [PPT] Recovering slideshow window")
        await self.wait_for_slideshow_window(timeout=10)

    async def next_slide(self) -> None:
        """
        Navigate to next slide in show.
        """

        def advance() -> None:
            if self.slide_show:
                try:
                    self.slide_show.Next()
                    logger.info("PowerPointController | Advanced to next slide.")
                except Exception as e:
                    logger.error(f"PowerPointController | Slide advance failed: {e}")

        await asyncio.to_thread(advance)

    async def prev_slide(self) -> None:
        """
        Navigate to previous slide in show.
        """

        def reverse() -> None:
            if self.slide_show:
                try:
                    self.slide_show.Previous()
                    logger.info("PowerPointController | Reverted to previous slide.")
                except Exception as e:
                    logger.error(f"PowerPointController | Slide revert failed: {e}")

        await asyncio.to_thread(reverse)

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

        def close() -> None:
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

        await asyncio.to_thread(close)
