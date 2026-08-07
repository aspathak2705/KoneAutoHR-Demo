import subprocess
import os
import time
import json
import asyncio
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
        self._audio_route = "teams-microphone"
        self._audio_input_device_name = ""
        self._audio_output_device_name = ""
        
        # Deterministic play state variables
        self._playing = False
        self._start_time = None
        self._total_duration_ms = 0.0
        self._pause_offset_ms = 0.0
        
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
            from app.modules.meeting_bot.config import meeting_bot_config
            self._audio_route = meeting_bot_config.audio_route
            self._audio_input_device_name = meeting_bot_config.audio_input_device_name
            self._audio_output_device_name = meeting_bot_config.audio_output_device_name
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

            # Resolve track duration from audio_manifest.json if possible, fallback to size/bitrate estimate
            duration = None
            try:
                from app.services.storage_service import storage_service
                import json
                session_dir = storage_service.get_session_dir(self.session_id)
                manifest_path = session_dir / "audio_manifest.json"
                if manifest_path.exists():
                    with open(manifest_path, "r", encoding="utf-8") as m_file:
                        manifest_data = json.load(m_file)
                    for track in manifest_data.get("tracks", []):
                        if track.get("filename", "").lower() == key:
                            duration = float(track.get("duration", 0))
                            break
            except Exception as e:
                logger.debug(f"AudioController | Manifest check failed: {e}")

            if not duration or duration <= 0:
                # Estimate: 1 second = ~16KB at typical mono TTS output bitrates
                try:
                    size_bytes = f.stat().st_size
                    duration = max(3.0, round(size_bytes / 16000.0, 1))
                except Exception:
                    duration = 5.0

            self._durations[key] = duration
            
        logger.info(f"AudioController | Zero-latency preloader completed caching {len(files)} tracks.")
    def validate_audio_route(self) -> bool:
        """Validate that the VB-CABLE Input playback device exists, is accessible, and cache its index."""
        from app.core.config import settings
        import sounddevice as sd
        
        target_name = settings.AUDIO_OUTPUT_DEVICE or "CABLE Input"
        devices = sd.query_devices()
        
        # Enumerate and log all detected output devices for troubleshooting
        logger.info("Detected Output Devices:")
        for idx, d in enumerate(devices):
            if d.get("max_output_channels", 0) > 0:
                logger.info(f"  [{idx}] {d.get('name')} (channels: {d.get('max_output_channels')})")
        
        # Find matching output device (matching case-insensitive prefix/substring)
        self._cached_device_idx = None
        selected_device_name = ""
        
        for idx, d in enumerate(devices):
            if d.get("max_output_channels", 0) > 0 and (
                target_name.lower() in d.get("name", "").lower() or
                d.get("name", "").lower().startswith(target_name.lower())
            ):
                self._cached_device_idx = idx
                selected_device_name = d.get("name")
                break
                
        if self._cached_device_idx is None:
            logger.error(f"[Audio] VB-CABLE playback device not found. Expected containing: {target_name}. Please install VB-Audio Virtual Cable.")
            raise RuntimeError(f"VB-CABLE playback device not found. Expected containing: {target_name}. Please install VB-Audio Virtual Cable.")
            
        # Verify device accessibility (try querying defaults or format support)
        try:
            sd.check_output_settings(device=self._cached_device_idx)
        except Exception as e:
            logger.error(f"[Audio] Selected device index {self._cached_device_idx} is not accessible: {e}")
            raise RuntimeError(f"Selected audio device '{selected_device_name}' is inaccessible: {e}")
            
        logger.info(
            f"Selected Output Device\n\n"
            f"CABLE Input\n"
            f"Index: {self._cached_device_idx}\n\n"
            f"Audio Validation Passed"
        )
        return True

    def play_narration(self, audio_path: Path, duration_ms: float = None) -> None:
        """
        Loads and starts playing narration.wav directly using sd.OutputStream callback for explicit lower latency control.
        """
        if getattr(self, "_cached_device_idx", None) is None:
            self.validate_audio_route()
        self.stop_audio()
        
        import sounddevice as sd
        import soundfile as sf
        import numpy as np
        
        logger.info(f"AudioController | Reading WAV file: {audio_path}")
        data, fs = sf.read(str(audio_path), dtype="float32")
        
        # Force stereo channel configuration if multi-channel, or mono if single-channel
        # Ensure 2D array representation for sounddevice output streams
        if len(data.shape) == 1:
            channels = 1
            data = data.reshape(-1, 1)
        else:
            channels = data.shape[1]
            
        duration_sec = len(data) / float(fs)
        
        # Verbose details logging
        logger.info(
            f"Audio Output Device : {getattr(self, '_cached_device_idx', 'Unknown')}\n"
            f"Device Index : {self._cached_device_idx}\n"
            f"Sample Rate : {fs} Hz\n"
            f"Channels : {channels}\n"
            f"Duration : {duration_sec:.2f} sec"
        )

        current_frame = 0

        def callback(outdata, frames, time_info, status):
            nonlocal current_frame
            if status:
                logger.warning(f"AudioController OutputStream Status: {status}")
            
            chunk_size = min(len(data) - current_frame, frames)
            if chunk_size > 0:
                outdata[:chunk_size] = data[current_frame:current_frame + chunk_size]
                outdata[chunk_size:] = 0
                current_frame += chunk_size
            else:
                outdata.fill(0)
                raise sd.CallbackStop

        # Initialize and start output stream
        self.stream = sd.OutputStream(
            samplerate=fs,
            channels=channels,
            device=self._cached_device_idx,
            callback=callback,
            dtype="float32"
        )
        self.stream.start()

        if duration_ms and duration_ms > 0:
            self._total_duration_ms = float(duration_ms)
        else:
            self._total_duration_ms = duration_sec * 1000.0

        self._start_time = time.time()
        self._playing = True
        self._pause_offset_ms = 0.0

    @property
    def playing(self) -> bool:
        """
        Exposes playback state.
        """
        if not self._playing:
            return False
        
        # If the sounddevice stream is still active, we are definitely playing
        if getattr(self, "stream", None) is not None:
            try:
                if self.stream.active:
                    return True
            except Exception:
                pass

        if self._start_time is None:
            return False
            
        elapsed = (time.time() - self._start_time) * 1000.0 + self._pause_offset_ms
        if elapsed >= self._total_duration_ms:
            self.stop_audio()
            return False
        return True

    def position(self) -> float:
        """
        Exposes current playback position in milliseconds.
        """
        if not self._playing or self._start_time is None:
            return self._pause_offset_ms
        elapsed = (time.time() - self._start_time) * 1000.0 + self._pause_offset_ms
        return min(elapsed, self._total_duration_ms)

    def stop_audio(self) -> None:
        if getattr(self, "stream", None) is not None:
            try:
                self.stream.stop()
                self.stream.close()
            except Exception:
                pass
            self.stream = None
        self._send_command("if ($active_player) { $active_player.Stop() };")
        self._playing = False
        self._start_time = None
        self._pause_offset_ms = 0.0
        self._total_duration_ms = 0.0
        if self.process:
            self.process.terminate()
            self.process = None

    def pause_audio(self) -> None:
        if self._playing and self._start_time is not None:
            self._pause_offset_ms = self.position()
            if getattr(self, "stream", None) is not None:
                try:
                    self.stream.stop()
                    self.stream.close()
                except Exception:
                    pass
                self.stream = None
            self._send_command("if ($active_player) { $active_player.Pause() };")
            self._playing = False
            self._start_time = None
            logger.info(f"AudioController | Audio playback paused at {self._pause_offset_ms:.0f}ms")

    def resume_audio(self) -> None:
        if not self._playing:
            self._start_time = time.time()
            self._playing = True
            self._send_command("if ($active_player) { $active_player.Play() };")
            logger.info(f"AudioController | Audio playback resumed from {self._pause_offset_ms:.0f}ms")

    def audio_ready(self) -> bool:
        from app.services.storage_service import storage_service
        session_dir = storage_service.get_session_dir(self.session_id)
        manifest_path = session_dir / "manifest.json"
        if not manifest_path.exists():
            return False
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)
            audio_file = manifest.get("audio", "narration.wav")
            audio_dir = storage_service.get_generated_audio_dir(self.session_id)
            return (session_dir / audio_file).exists() or (session_dir / "audio" / audio_file).exists() or (audio_dir / audio_file).exists()
        except Exception:
            return False


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


