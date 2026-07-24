import shutil
from pathlib import Path
from loguru import logger
from app.core.task_registry import async_task_registry
from app.modules.meeting_bot.services.meeting_bot_service import meeting_bot_service
from app.modules.meeting_bot.media.audio_controller import cleanup_audio_controller
from app.modules.presentation_observer.services.presentation_observer_service import presentation_observer_service
from app.modules.semantic_browser.services.semantic_browser_service import semantic_browser_service
from app.services.runtime_service import runtime_service
from app.services.storage_service import storage_service

class CleanupManager:
    async def cleanup_session(self, session_id: str) -> None:
        """
        One central shutdown sequence:
        Session Cleanup -> Cancel Tasks -> Stop Audio -> Close Browser -> Dispose Observer -> Remove Coordinator -> Delete Profile
        """
        logger.info(f"CleanupManager | Initiating shutdown sequence for Session: {session_id}...")

        # 1. Cancel registered background tasks
        try:
            async_task_registry.cancel_all(session_id)
        except Exception as e:
            logger.error(f"CleanupManager | Error cancelling tasks: {e}")

        # 2. Stop audio process
        try:
            cleanup_audio_controller(session_id)
        except Exception as e:
            logger.error(f"CleanupManager | Error stopping audio: {e}")

        # 3. Close & remove MeetingBot (stops Playwright/browser/page contexts)
        try:
            await meeting_bot_service.stop_bot(session_id)
        except Exception as e:
            logger.error(f"CleanupManager | Error stopping meeting bot: {e}")

        # 4. Dispose Observer registry
        try:
            presentation_observer_service.remove_observer(session_id)
        except Exception as e:
            logger.error(f"CleanupManager | Error removing observer: {e}")

        # 5. Dispose Semantic Browser registry
        try:
            semantic_browser_service.remove_history(session_id)
        except Exception as e:
            logger.error(f"CleanupManager | Error removing semantic history: {e}")

        # 6. Remove RuntimeCoordinator
        try:
            runtime_service.remove_coordinator(session_id)
        except Exception as e:
            logger.error(f"CleanupManager | Error removing coordinator: {e}")

        # 7. Delete Browser profile directory (cleanup disk usage)
        try:
            profile_dir = storage_service.get_session_dir(session_id) / "profile"
            if profile_dir.exists():
                shutil.rmtree(profile_dir, ignore_errors=True)
                logger.info(f"CleanupManager | Deleted unique profile dir: {profile_dir}")
        except Exception as e:
            logger.error(f"CleanupManager | Error deleting profile dir: {e}")

        logger.info(f"CleanupManager | Shutdown sequence completed for Session: {session_id}.")

cleanup_manager = CleanupManager()
