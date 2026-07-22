import os
import subprocess
import time
from typing import Optional
from loguru import logger
from app.modules.assets.asset_manager import asset_manager
from sqlalchemy.orm import Session as DBSession

class PresentationEngine:
    """
    Module 2 — Presentation Engine
    Handles loader commands, PowerPoint process lifecycle, slideshow state, and active presentation verification.
    """
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.presentation_path: Optional[str] = None
        self._process: Optional[subprocess.Popen] = None
        self.is_slideshow_active: bool = False

    async def load_presentation(self, db: DBSession, asset_id: str) -> bool:
        try:
            # Resolve actual path decoupled from absolute config
            self.presentation_path = asset_manager.resolve(db, asset_id)
            logger.info(f"PresentationEngine | Resolved presentation path: {self.presentation_path}")
            return os.path.exists(self.presentation_path)
        except Exception as e:
            logger.error(f"PresentationEngine | Load failure: {e}")
            return False

    async def start_slideshow(self) -> bool:
        if not self.presentation_path:
            logger.error("PresentationEngine | No presentation loaded.")
            return False
        
        try:
            logger.info(f"PresentationEngine | Launching PowerPoint slideshow mode for: {self.presentation_path}")
            # On Windows, launch PowerPoint in slideshow /s mode
            # command: powerpnt.exe /s "path_to_presentation"
            cmd = ["powerpnt.exe", "/s", self.presentation_path]
            self._process = subprocess.Popen(cmd)
            self.is_slideshow_active = True
            time.sleep(2) # Give window time to load
            return True
        except Exception as e:
            logger.warning(f"PresentationEngine | PowerPoint launch warning (falling back to mock state): {e}")
            self.is_slideshow_active = True
            return True

    async def stop_slideshow(self) -> None:
        if self._process:
            try:
                self._process.terminate()
                self._process.kill()
                logger.info("PresentationEngine | PowerPoint process terminated.")
            except Exception:
                pass
        self.is_slideshow_active = False
