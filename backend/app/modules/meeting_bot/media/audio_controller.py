import subprocess
import os
from pathlib import Path
from loguru import logger

class AudioController:
    def __init__(self, session_id: str):
        self.session_id = session_id
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
            if not os.path.isabs(p) or os.path.exists(p):
                return p
        return "powershell"

    def play_audio(self, audio_path: str) -> None:
        """
        Plays MP3 audio file using native Windows Media player in background process.
        """
        self.stop_audio()

        # Secure sandbox path resolution
        from app.services.storage_service import storage_service
        base_dir = storage_service.get_session_dir(self.session_id) / "audio"
        base_dir = base_dir.resolve()
        
        # Guard against traversal (e.g. absolute paths or ../ paths)
        target_path = Path(base_dir / audio_path).resolve()
        if not str(target_path).startswith(str(base_dir)):
            raise ValueError(f"Security Warning: Audio path traversal attempt blocked: {audio_path}")

        if not target_path.exists():
            logger.error(f"AudioController | File not found: {target_path}")
            return

        logger.info(f"AudioController | Session: {self.session_id} | Playing: {target_path}")
        self.current_track = audio_path

        # PowerShell media player script routing to system speaker
        ps_cmd = (
            f'$player = New-Object System.Media.SoundPlayer; '
            f'$player.SoundLocation = "{str(target_path)}"; '
            f'$player.PlaySync();'
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
            logger.info(f"AudioController | Session: {self.session_id} | Stopping audio playback.")
            try:
                self.process.terminate()
                self.process.wait(timeout=2)
            except Exception:
                try:
                    self.process.process.kill()
                except Exception:
                    pass
            self.process = None
            self.current_track = None

    def pause_audio(self) -> None:
        self.stop_audio()

    def resume_audio(self) -> None:
        if self.current_track:
            self.play_audio(self.current_track)

# Isolated AudioController registry per session ID
_audio_controllers = {}

def get_audio_controller(session_id: str) -> AudioController:
    if session_id not in _audio_controllers:
        _audio_controllers[session_id] = AudioController(session_id)
    return _audio_controllers[session_id]

def cleanup_audio_controller(session_id: str) -> None:
    ctrl = _audio_controllers.pop(session_id, None)
    if ctrl:
        ctrl.stop_audio()
