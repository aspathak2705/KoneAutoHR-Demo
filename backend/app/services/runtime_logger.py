import os
import datetime
from pathlib import Path
from app.services.storage_service import storage_service
from loguru import logger

class RuntimeLogger:
    def _get_log_file(self, session_id: str) -> Path:
        reports_dir = storage_service.get_reports_dir(session_id)
        log_file = reports_dir / "runtime_execution.log"
        return log_file

    def log_event(self, session_id: str, event_name: str, message: str, level: str = "INFO") -> None:
        """
        Sprint RC-6: Core logger writing meeting, speech, warning, and recovery operations.
        """
        timestamp = datetime.datetime.now().isoformat()
        log_entry = f"[{timestamp}] [{level}] [{event_name}] {message}\n"
        
        # Log to standard loguru console/file
        log_func = getattr(logger, level.lower(), logger.info)
        log_func(f"RuntimeLogger | Session: {session_id} | [{event_name}] {message}")

        try:
            log_path = self._get_log_file(session_id)
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(log_entry)
        except Exception as e:
            logger.error(f"RuntimeLogger | Failed to write log file: {e}")

    def log_meeting(self, session_id: str, message: str) -> None:
        self.log_event(session_id, "MEETING", message, "INFO")

    def log_speech(self, session_id: str, message: str) -> None:
        self.log_event(session_id, "SPEECH", message, "INFO")

    def log_error(self, session_id: str, message: str) -> None:
        self.log_event(session_id, "ERROR", message, "ERROR")

    def log_warning(self, session_id: str, message: str) -> None:
        self.log_event(session_id, "WARNING", message, "WARNING")

    def log_recovery(self, session_id: str, message: str) -> None:
        self.log_event(session_id, "RECOVERY", message, "INFO")

runtime_logger = RuntimeLogger()
