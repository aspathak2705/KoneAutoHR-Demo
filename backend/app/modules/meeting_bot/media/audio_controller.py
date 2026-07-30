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

        # PowerShell media player script routing to system speaker (supporting MP3 playback)
        ps_cmd = (
            f'Add-Type -AssemblyName PresentationCore; '
            f'$player = New-Object System.Windows.Media.MediaPlayer; '
            f'$player.Open([Uri]"{target_path.as_uri()}"); '
            f'$player.Play(); '
            f'Start-Sleep -Milliseconds 500; '
            f'while ($player.NaturalDuration.HasTimeSpan -eq $false) {{ Start-Sleep -Milliseconds 100 }}; '
            f'Start-Sleep -Milliseconds ($player.NaturalDuration.TimeSpan.TotalMilliseconds - 500);'
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

    def audio_ready(self) -> bool:
        """
        Verifies if all narration assets exist on disk and are successfully loaded into the AudioController.
        """
        from app.services.storage_service import storage_service
        from app.db.database import SessionLocal
        from app.models.presentation_script import PresentationScript
        from app.models.session import Session
        import json
        
        audio_dir = storage_service.get_session_dir(self.session_id) / "audio"
        if not audio_dir.exists():
            return False
            
        # Read script from db to identify expected files
        with SessionLocal() as db:
            sess = db.query(Session).filter(Session.id == self.session_id).first()
            if not sess or not sess.presentation_id:
                return False
            script = db.query(PresentationScript).filter(
                PresentationScript.presentation_id == sess.presentation_id,
                PresentationScript.status == "ACTIVE"
            ).first()
            if not script:
                return False
            try:
                payload = json.loads(script.script_content)
            except Exception:
                return False
                
        # Identify expected files
        expected = []
        opening = payload.get("opening") or {}
        welcome_flow = payload.get("welcome_flow") or {}
        
        if opening.get("greeting") or welcome_flow.get("greeting"):
            expected.append("greeting.mp3")
        if opening.get("presenter_intro") or welcome_flow.get("intro"):
            expected.append("intro.mp3")
        if opening.get("employee_welcome"):
            expected.append("employee_welcome.mp3")
        if opening.get("audio_check") or welcome_flow.get("audio_check"):
            expected.append("audio_check.mp3")
        if opening.get("ice_breaker") or welcome_flow.get("ice_breaker"):
            expected.append("ice_breaker.mp3")
        if opening.get("session_rules") or welcome_flow.get("rules"):
            expected.append("session_rules.mp3")
        if opening.get("agenda"):
            expected.append("agenda.mp3")
            
        slides = payload.get("slides")
        if isinstance(slides, list):
            for s in slides:
                num = int(s.get("slide_number", 1))
                if s.get("objective"):
                    expected.append(f"slide_{num}_objective.mp3")
                if s.get("transition_in"):
                    expected.append(f"slide_{num}_transition_in.mp3")
                if s.get("narration"):
                    expected.append(f"slide_{num}.mp3")
                    expected.append(f"slide_{num}_narration.mp3")
                if s.get("understanding_check"):
                    expected.append(f"slide_{num}_understanding_check.mp3")
                if s.get("transition_out"):
                    expected.append(f"slide_{num}_transition_out.mp3")
        else:
            slide_narrations = payload.get("slide_narrations", {})
            for num_str, data in slide_narrations.items():
                num = int(num_str)
                if data.get("narration"):
                    expected.append(f"slide_{num}.mp3")
                    expected.append(f"slide_{num}_narration.mp3")
                    
        closing = payload.get("closing") or {}
        closing_script = payload.get("closing_script") or {}
        if closing.get("summary") or closing_script.get("summary"):
            expected.append("closing.mp3")
        if closing.get("next_steps") or closing_script.get("next_steps"):
            expected.append("closing_next_steps.mp3")
        if closing.get("farewell"):
            expected.append("closing_farewell.mp3")
            
        if not expected:
            return False
            
        # Verify all expected exist
        for filename in expected:
            if not (audio_dir / filename).exists():
                return False
                
        return True

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
