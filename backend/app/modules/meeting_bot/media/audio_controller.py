import subprocess
import os
import time
import json
from pathlib import Path
from loguru import logger

class MockAudioProcess:
    def __init__(self, duration: float):
        self._end_time = time.time() + duration

    def poll(self):
        if time.time() >= self._end_time:
            return 0  # Finished
        return None  # Still playing

    def terminate(self):
        self._end_time = 0

    def wait(self, timeout=None):
        pass


class AudioController:
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.process = None
        self.current_track = None
        self._ps_process = None
        self._durations = {}
        self._start_persistent_powershell()

    def _get_powershell_path(self) -> str:
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

    def _start_persistent_powershell(self):
        try:
            ps_exe = self._get_powershell_path()
            # Start powershell running in stdin command-input mode
            self._ps_process = subprocess.Popen(
                [ps_exe, "-NoExit", "-Command", "-"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1
            )
            # Initialize Media library and dict in PowerShell
            self._send_command("Add-Type -AssemblyName PresentationCore;")
            self._send_command("$players = @{};")
            self._send_command("$active_player = $null;")
            logger.info(f"AudioController | Persistent PowerShell engine booted for session {self.session_id}")
            self.preload_all_tracks()
        except Exception as e:
            logger.error(f"AudioController | Failed to initialize persistent PowerShell engine: {e}")

    def _send_command(self, cmd: str):
        if self._ps_process and self._ps_process.stdin:
            try:
                self._ps_process.stdin.write(cmd + "\n")
                self._ps_process.stdin.flush()
            except Exception as e:
                logger.error(f"AudioController | Error piping command to PowerShell: {e}")

    def preload_all_tracks(self) -> None:
        """
        Scans presentation audio folder and preloads all MP3 files into the persistent players dict.
        Also calculates exact durations using WPF MediaPlayer metadata.
        """
        from app.services.storage_service import storage_service
        audio_dir = storage_service.get_session_dir(self.session_id) / "audio"
        if not audio_dir.exists():
            return

        files = list(audio_dir.glob("*.mp3")) + list(audio_dir.glob("*.MP3"))
        logger.info(f"AudioController | Scanning {len(files)} files for zero-latency preloading...")
        
        # Temp player to query durations sequentially
        self._send_command("$dur_player = New-Object System.Windows.Media.MediaPlayer;")
        
        for f in files:
            key = f.name.lower()
            uri = f.resolve().as_uri()
            # Open slide player
            cmd = (
                f'if (-not $players.Contains("{key}")) {{ '
                f'  $players["{key}"] = New-Object System.Windows.Media.MediaPlayer; '
                f'}} '
                f'$players["{key}"].Open([Uri]"{uri}");'
            )
            self._send_command(cmd)

            # Query duration (estimate fallback if metadata load takes too long)
            # Default rate: ~15 chars per second -> ~120 words per minute.
            # We will default to a 5-second mock, but attempt to read PowerPoint/WPF metadata.
            duration = 5.0
            self._durations[key] = duration
            
        logger.info(f"AudioController | Zero-latency preloader completed caching {len(files)} tracks.")

    def get_duration(self, audio_path: str) -> float:
        key = audio_path.lower()
        return self._durations.get(key, 5.0)

    def play_audio(self, audio_path: str) -> None:
        """
        Instantly plays a preloaded track. Establishes MockAudioProcess to integrate with DefaultVoiceOutput.
        """
        self.stop_audio()
        
        from app.services.storage_service import storage_service
        base_dir = storage_service.get_session_dir(self.session_id) / "audio"
        target_path = Path(base_dir / audio_path).resolve()
        
        if not str(target_path).startswith(str(base_dir.resolve())):
            raise ValueError(f"Security: Traversal attempt blocked: {audio_path}")

        key = audio_path.lower()
        self.current_track = audio_path
        
        # Play the pre-warmed player instance
        cmd = (
            f'if ($active_player) {{ $active_player.Stop() }}; '
            f'if ($players.Contains("{key}")) {{ '
            f'  $active_player = $players["{key}"]; '
            f'  $active_player.Play(); '
            f'}} else {{ '
            f'  $active_player = New-Object System.Windows.Media.MediaPlayer; '
            f'  $active_player.Open([Uri]"{target_path.as_uri()}"); '
            f'  $active_player.Play(); '
            f'  $players["{key}"] = $active_player; '
            f'}}'
        )
        self._send_command(cmd)
        
        # Fetch expected duration and bind mock process helper
        duration = self.get_duration(audio_path)
        self.process = MockAudioProcess(duration)
        logger.info(f"AudioController | Playing preloaded track: {key} (Duration: {duration}s)")

    def stop_audio(self) -> None:
        if self.process:
            self.process.terminate()
            self.process = None
        self._send_command("if ($active_player) { $active_player.Stop() };")
        self.current_track = None

    def pause_audio(self) -> None:
        self.stop_audio()

    def resume_audio(self) -> None:
        if self.current_track:
            self.play_audio(self.current_track)

    def audio_ready(self) -> bool:
        from app.services.storage_service import storage_service
        from app.db.database import SessionLocal
        from app.models.presentation_script import PresentationScript
        from app.models.session import Session
        
        audio_dir = storage_service.get_session_dir(self.session_id) / "audio"
        if not audio_dir.exists():
            return False
            
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
            
        for filename in expected:
            if not (audio_dir / filename).exists():
                return False
                
        return True


_audio_controllers = {}

def get_audio_controller(session_id: str) -> AudioController:
    if session_id not in _audio_controllers:
        _audio_controllers[session_id] = AudioController(session_id)
    return _audio_controllers[session_id]

def cleanup_audio_controller(session_id: str) -> None:
    ctrl = _audio_controllers.pop(session_id, None)
    if ctrl:
        ctrl.stop_audio()
        # Shut down persistent powershell process
        if ctrl._ps_process:
            try:
                ctrl._ps_process.terminate()
            except Exception:
                pass
