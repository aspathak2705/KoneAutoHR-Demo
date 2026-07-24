import asyncio
from typing import Dict, Set
from loguru import logger

class BackgroundTaskRegistry:
    def __init__(self):
        # Maps session_id -> Set of asyncio.Task
        self._tasks: Dict[str, Set[asyncio.Task]] = {}

    def register(self, session_id: str, task: asyncio.Task) -> None:
        """
        Registers a background asyncio task for a given session.
        """
        if session_id not in self._tasks:
            self._tasks[session_id] = set()
        
        self._tasks[session_id].add(task)
        # Automatically discard done tasks
        task.add_done_callback(lambda t: self._tasks.get(session_id, set()).discard(t))
        logger.info(f"TaskRegistry | Registered task {task.get_name()} for Session: {session_id}")

    def cancel_all(self, session_id: str) -> None:
        """
        Cancels all registered tasks for a given session.
        """
        tasks = self._tasks.pop(session_id, set())
        if tasks:
            logger.info(f"TaskRegistry | Cancelling {len(tasks)} tasks for Session: {session_id}")
            for task in tasks:
                if not task.done():
                    task.cancel()

async_task_registry = BackgroundTaskRegistry()
