import os
from pathlib import Path
from loguru import logger
from app.core.config import settings

class VerificationEngine:
    def verify_package(self, session_id: str, package_data: dict) -> bool:
        """
        Validates the compiled Presentation Package.
        Checks existence, non-zero size, and parameters of script and audio files.
        """
        logger.info(f"VerificationEngine | Verifying package integrity for session {session_id}")
        
        # 1. Check session.json exists in package
        slides = package_data.get("slide_knowledge", [])
        if len(slides) == 0:
            raise ValueError("Verification Failed: Slide deck has zero slides or was not parsed.")

        # 2. Check script contents
        script = package_data.get("script", {})
        if not script or not script.get("opening") or not script.get("slides"):
            raise ValueError("Verification Failed: Session script is missing welcome flows or slide narration blocks.")

        # 3. Check pre-generated audio files
        audio_meta = package_data.get("audio_metadata", [])
        if len(audio_meta) == 0:
            raise ValueError("Verification Failed: No audio files generated for presentation package.")

        base_upload = Path(settings.UPLOAD_DIR)
        for audio in audio_meta:
            rel_path = audio.get("path")
            if not rel_path:
                raise ValueError("Verification Failed: Audio metadata missing file path reference.")
                
            full_path = base_upload / rel_path
            if not full_path.exists():
                raise ValueError(f"Verification Failed: Pre-generated audio file is missing from storage: {rel_path}")
                
            if full_path.stat().st_size == 0:
                raise ValueError(f"Verification Failed: Pre-generated audio file is corrupted or empty: {rel_path}")
                
            if not audio.get("duration") or audio.get("duration") <= 0:
                raise ValueError(f"Verification Failed: Audio duration metric is missing or invalid: {rel_path}")

        logger.info(f"VerificationEngine | Package verified successfully. Ready for runtime.")
        return True

verification_engine = VerificationEngine()
