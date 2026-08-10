import os
import json
from pathlib import Path
from typing import Dict, Any, Tuple
from loguru import logger
from sqlalchemy.orm import Session as DBSession

from app.models.presentation import Presentation
from app.models.presentation_script import PresentationScript
from app.models.presentation_question import PresentationQuestion
from app.services.storage_service import storage_service

class PresentationAssetManager:
    """
    Presentation Asset Manager
    Centralizes availability checks for reusable presentation assets (Script, Narration, Timeline, Manifest, Package).
    Avoids openrouter or sarvam regeneration if files are already generated.
    """

    def get_asset_paths(self, presentation_id: str, mode: str = "AI") -> Dict[str, Path]:
        """
        Returns structured paths for presentation assets in storage/presentations/{presentation_id}/[AI|HR]/.
        """
        # Store presentation-specific assets in dedicated mode folders inside storage/uploads/presentations/
        pres_dir = storage_service.presentations_dir / presentation_id / mode
        pres_dir.mkdir(parents=True, exist_ok=True)
        return {
            "dir": pres_dir,
            "script": pres_dir / "script.json",
            "narration": pres_dir / "narration.wav",
            "timeline": pres_dir / "presentation_timeline.json",
            "manifest": pres_dir / "manifest.json",
            "slides_dir": pres_dir / "presentation_assets" / "slides"
        }

    def check_assets(self, db: DBSession, presentation_id: str, mode: str = "AI") -> Dict[str, bool]:
        """
        Scans DB and disk to verify status of presentation assets.
        """
        paths = self.get_asset_paths(presentation_id, mode)
        
        # Check script (DB first, then fallback file check)
        script_row = db.query(PresentationScript).filter(
            PresentationScript.presentation_id == presentation_id,
            PresentationScript.status == "ACTIVE"
        ).first()
        script_exists = script_row is not None and bool(script_row.script_content)
        if not script_exists:
            script_exists = paths["script"].exists()

        # Check narration file on disk
        narration_exists = paths["narration"].exists() and paths["narration"].stat().st_size > 0

        # Check timeline file
        timeline_exists = paths["timeline"].exists() and paths["timeline"].stat().st_size > 0

        # Check manifest file
        manifest_exists = paths["manifest"].exists() and paths["manifest"].stat().st_size > 0

        # Check if the slide deck extraction thumbnails exist
        slides_exist = paths["slides_dir"].exists() and any(paths["slides_dir"].glob("slide_*.png"))

        return {
            "script_exists": script_exists,
            "narration_exists": narration_exists,
            "timeline_exists": timeline_exists,
            "manifest_exists": manifest_exists,
            "slides_exist": slides_exist
        }

    def get_asset_status(self, db: DBSession, presentation_id: str, mode: str = "AI") -> Dict[str, Any]:
        """
        Returns rich status info.
        """
        checks = self.check_assets(db, presentation_id, mode)
        return {
            "presentation_id": presentation_id,
            **checks
        }

    def invalidate_asset(self, presentation_id: str, asset_type: str, mode: str = "AI") -> None:
        """
        Removes generated files for regenerations.
        Follows upstream dependency chain invalidations:
        Script -> Narration -> Timeline -> Manifest
        """
        paths = self.get_asset_paths(presentation_id, mode)
        to_invalidate = []

        if asset_type == "script":
            to_invalidate = ["script", "narration", "timeline", "manifest"]
        elif asset_type == "narration":
            to_invalidate = ["narration", "timeline", "manifest"]
        elif asset_type == "timeline":
            to_invalidate = ["timeline", "manifest"]
        else:
            to_invalidate = [asset_type]

        for a_type in to_invalidate:
            if a_type in paths and paths[a_type].exists():
                try:
                    paths[a_type].unlink()
                    logger.info(f"PresentationAssetManager | Invalidated/deleted {a_type} due to dependency trigger on {asset_type} for presentation {presentation_id} in {mode} mode")
                except Exception as e:
                    logger.error(f"PresentationAssetManager | Failed to delete {a_type} file: {e}")

presentation_asset_manager = PresentationAssetManager()
