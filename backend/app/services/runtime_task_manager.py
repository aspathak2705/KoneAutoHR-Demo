import asyncio
from typing import Dict, Optional
from loguru import logger

class RuntimeTaskManager:
    """
    Sprint RS-1 — Runtime Task Management & Deduplication (Thread/Task Safe Atomic Registration)
    Guarantees: One Session -> One Runtime -> One Browser -> One Active Task.
    """
    def __init__(self):
        self._active_tasks: Dict[str, asyncio.Task] = {}
        self._lock = asyncio.Lock()

    def is_task_active(self, session_id: str) -> bool:
        task = self._active_tasks.get(session_id)
        return task is not None and not task.done()

    async def register_task_atomic(self, session_id: str, task: asyncio.Task) -> bool:
        """
        Atomic task check-and-set to eliminate race conditions across concurrent API/scheduler calls.
        """
        async with self._lock:
            if self.is_task_active(session_id):
                logger.warning(f"RuntimeTaskManager | Session {session_id} already has an active task. Atomic registration rejected.")
                return False
            self._active_tasks[session_id] = task
            logger.info(f"RuntimeTaskManager | Atomically registered active task for session {session_id}.")
            return True

    def register_task(self, session_id: str, task: asyncio.Task) -> bool:
        if self.is_task_active(session_id):
            logger.warning(f"RuntimeTaskManager | Session {session_id} already has an active task. Registration rejected.")
            return False
        self._active_tasks[session_id] = task
        logger.info(f"RuntimeTaskManager | Registered active task for session {session_id}.")
        return True

    def cancel_task(self, session_id: str) -> bool:
        task = self._active_tasks.pop(session_id, None)
        if task and not task.done():
            task.cancel()
            logger.info(f"RuntimeTaskManager | Cancelled active task for session {session_id}.")
            return True
        return False

    def cleanup_task(self, session_id: str) -> None:
        if session_id in self._active_tasks:
            self._active_tasks.pop(session_id, None)
            logger.info(f"RuntimeTaskManager | Cleaned up task record for session {session_id}.")

runtime_task_manager = RuntimeTaskManager()
