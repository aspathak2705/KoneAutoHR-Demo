import os
import asyncio
from pathlib import Path
from loguru import logger

class PowerPointController:
    def __init__(self):
        self.powerpoint = None
        self.presentation = None
        self.slide_show = None

    async def open_slideshow(self, ppt_path: str) -> None:
        """
        Open PowerPoint presentation and start a windowed slideshow.
        """
        def start() -> None:
            import pythoncom
            import win32com.client
            import subprocess

            # Clean existing PowerPoint instances to avoid locks/read-only prompts
            try:
                subprocess.run(["taskkill", "/f", "/im", "powerpnt.exe"], capture_output=True)
            except Exception:
                pass

            pythoncom.CoInitialize()
            self.powerpoint = win32com.client.Dispatch("PowerPoint.Application")
            self.powerpoint.Visible = True

            # Minimize main window so slideshow is focus target
            try:
                self.powerpoint.WindowState = 2  # ppWindowMinimized
            except Exception as e:
                logger.warning(f"PowerPointController | Could not minimize PowerPoint window: {e}")

            abs_ppt = str(Path(ppt_path).resolve())
            self.presentation = self.powerpoint.Presentations.Open(
                abs_ppt,
                ReadOnly=True,
                WithWindow=True
            )
            self.presentation.SlideShowSettings.ShowType = 2  # ppShowTypeWindow
            self.presentation.SlideShowSettings.Run()
            self.slide_show = self.presentation.SlideShowWindow.View

        await asyncio.to_thread(start)
        await asyncio.sleep(2)
        await self.focus_slideshow_window()

    async def focus_slideshow_window(self) -> None:
        """
        Activate and focus the slideshow presentation window to prepare for chrome window sharing.
        """
        def activate():
            import win32gui
            import win32con

            hwnd = win32gui.FindWindow("screenClass", None)
            if not hwnd:
                def enum_cb(h, extra):
                    title = win32gui.GetWindowText(h)
                    if "PowerPoint Slide Show" in title:
                        extra.append(h)
                    return True
                hwnds = []
                win32gui.EnumWindows(enum_cb, hwnds)
                if hwnds:
                    hwnd = hwnds[0]

            if hwnd:
                logger.info(f"PowerPointController | Found slideshow window: {hwnd}. Activating.")
                try:
                    win32gui.ShowWindow(hwnd, win32con.SW_SHOWNORMAL)
                    win32gui.SetForegroundWindow(hwnd)
                except Exception as ex:
                    logger.warning(f"PowerPointController | Failed to bring slideshow window to foreground: {ex}")
            else:
                logger.warning("PowerPointController | Slideshow window not found.")

        await asyncio.to_thread(activate)
        await asyncio.sleep(1)

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
