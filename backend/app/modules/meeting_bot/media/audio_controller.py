import subprocess
import os
from pathlib import Path
from loguru import logger

class AudioController:
    def __init__(self):
        self.process = None
        self.current_track = None

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

        self.process = subprocess.Popen(
            ["powershell", "-Command", ps_cmd],
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
