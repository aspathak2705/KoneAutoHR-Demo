import asyncio
import datetime
from typing import Dict, Any, Optional
from loguru import logger
from app.db.database import SessionLocal
from app.models.runtime import Runtime

class RuntimeMonitor:
    """
    Stage 9 — Runtime Monitor
    Monitors meeting connection health, heartbeat, and browser driver status during presentation runs.
    Pauses presentation state on connection drops and triggers recovery.
    """
    def __init__(self, session_id: str):
        self.session_id = session_id
        self._is_monitoring: bool = False

    def is_health_ok(self) -> bool:
        with SessionLocal() as db:
            runtime = db.query(Runtime).filter(Runtime.session_id == self.session_id).first()
            if not runtime:
                return False
            if runtime.state in ["FAILED", "DISCONNECTED"]:
                return False
            if runtime.last_heartbeat:
                stale_seconds = (datetime.datetime.now() - runtime.last_heartbeat).total_seconds()
                if stale_seconds > 30:
                    logger.warning(f"RuntimeMonitor | Session {self.session_id} heartbeat is stale ({stale_seconds:.1f}s).")
                    return False
            return True

    async def monitor_loop(self, orchestrator) -> None:
        self._is_monitoring = True
        logger.info(f"RuntimeMonitor | Started health monitoring loop for session {self.session_id}.")
        while self._is_monitoring:
            await asyncio.sleep(5)
            if not self.is_health_ok():
                logger.warning(f"RuntimeMonitor | Health issue detected for session {self.session_id}. Pausing presentation...")
                orchestrator.pause_presentation()

    def stop_monitoring(self) -> None:
        self._is_monitoring = False
        logger.info(f"RuntimeMonitor | Stopped health monitoring for session {self.session_id}.")
