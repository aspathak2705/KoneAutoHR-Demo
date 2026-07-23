import subprocess
import os
from pathlib import Path
from loguru import logger

class AudioController:
    def __init__(self):
        self.process = None
        self.current_track = None

    def _get_powershell_path(self) -> str:
        """
        Retrieves the absolute path to PowerShell.exe to prevent FileNotFoundError.
        """
        system_root = os.environ.get("SystemRoot", "C:\\Windows")
        paths = [
            os.path.join(system_root, "System32", "WindowsPowerShell", "v1.0", "powershell.exe"),
            os.path.join(system_root, "SysWOW64", "WindowsPowerShell", "v1.0", "powershell.exe"),
            "powershell.exe",
            "powershell"
        ]
        for p in paths:
            # If it's a relative/executable name, assume it works if absolute doesn't exist
            if not os.path.isabs(p) or os.path.exists(p):
                return p
        return "powershell"

    def play_audio(self, audio_path: str) -> None:
        """
        Plays MP3 audio file using native Windows Media player in background process.
        """
        self.stop_audio()
        
        path = Path(audio_path).resolve()
        if not path.exists():
            logger.error(f"AudioController | File not found: {audio_path}")
            return
            
        logger.info(f"AudioController | Playing: {path}")
        self.current_track = audio_path

        # PowerShell media player script
        ps_cmd = (
            f'Add-Type -AssemblyName PresentationCore; '
            f'$player = New-Object System.Windows.Media.MediaPlayer; '
            f'$player.Open("{str(path)}"); '
            f'$player.Play(); '
            f'while ($player.Position -lt $player.NaturalDuration.TimeSpan) {{ Start-Sleep -Milliseconds 200 }}'
        )

        ps_exe = self._get_powershell_path()
        self.process = subprocess.Popen(
            [ps_exe, "-Command", ps_cmd],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

    def stop_audio(self) -> None:
        """
        Kills the playback process.
        """
        if self.process:
            logger.info("AudioController | Stopping audio playback.")
            try:
                self.process.terminate()
                self.process.wait(timeout=2)
            except Exception:
                try:
                    self.process.kill()
                except Exception:
                    pass
            self.process = None
            self.current_track = None

    def pause_audio(self) -> None:
        self.stop_audio()

    def resume_audio(self) -> None:
        if self.current_track:
            self.play_audio(self.current_track)

audio_controller = AudioController()
