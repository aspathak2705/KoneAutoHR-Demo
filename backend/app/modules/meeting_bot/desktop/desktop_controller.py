import ctypes
import time
from loguru import logger

# Load Win32 user32
try:
    user32 = ctypes.windll.user32
except Exception:
    user32 = None

class DesktopController:
    def focus_teams(self) -> bool:
        """
        Finds the Microsoft Teams Chromium browser window and focuses it.
        """
        if not user32:
            logger.warning("DesktopController | Win32 user32 not loaded.")
            return False

        logger.info("DesktopController | Attempting to focus Teams window...")
        hwnd = user32.FindWindowW(None, "Microsoft Teams")
        if not hwnd:
            hwnd = self._find_window_by_title_substring("Teams")

        if hwnd:
            user32.ShowWindow(hwnd, 9)  # SW_RESTORE
            user32.SetForegroundWindow(hwnd)
            logger.info("DesktopController | Focused Teams window successfully.")
            return True
        logger.warning("DesktopController | Teams window not found.")
        return False

    def _find_window_by_title_substring(self, title_substring: str) -> int:
        if not user32:
            return 0
            
        hwnd_found = [0]
        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_void_p)
        
        def enum_windows_callback(hwnd, lParam):
            length = user32.GetWindowTextLengthW(hwnd)
            if length > 0:
                buf = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buf, length + 1)
                if title_substring.lower() in buf.value.lower():
                    hwnd_found[0] = hwnd
                    return False
            return True

        user32.EnumWindows(WNDENUMPROC(enum_windows_callback), 0)
        return hwnd_found[0]

    def press_enter(self) -> None:
        """
        Simulates pressing the ENTER key.
        """
        if not user32:
            return
        logger.info("DesktopController | Simulating keystroke: ENTER")
        user32.keybd_event(0x0D, 0, 0, 0)
        time.sleep(0.05)
        user32.keybd_event(0x0D, 0, 2, 0)

    def dismiss_popup(self) -> None:
        """
        Simulates pressing ESC to dismiss modals.
        """
        if not user32:
            return
        logger.info("DesktopController | Simulating popup dismissal: ESC")
        user32.keybd_event(0x1B, 0, 0, 0)
        time.sleep(0.05)
        user32.keybd_event(0x1B, 0, 2, 0)

    def paste_text(self, text: str) -> None:
        """
        Sets text to clipboard and pastes it using Control+V.
        """
        if not user32:
            return
        logger.info("DesktopController | Simulating text paste...")
        import subprocess
        # Escaping quotes for PowerShell
        escaped = text.replace("'", "''")
        subprocess.run(
            ["powershell", "-Command", f"Set-Clipboard -Value '{escaped}'"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        
        time.sleep(0.1)
        user32.keybd_event(0x11, 0, 0, 0)  # Ctrl
        user32.keybd_event(0x56, 0, 0, 0)  # V
        time.sleep(0.05)
        user32.keybd_event(0x56, 0, 2, 0)
        user32.keybd_event(0x11, 0, 2, 0)

desktop_controller = DesktopController()
