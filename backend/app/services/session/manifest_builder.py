import json
from pathlib import Path
from loguru import logger

class ManifestBuilder:
    def build_manifest(
        self,
        session_id: str,
        presentation_filename: str,
        audio_filename: str,
        timeline_filename: str,
        duration_ms: float,
        slide_count: int,
        session_dir: Path
    ) -> Path:
        """
        Generates standard manifest.json.
        """
        manifest_data = {
            "version": "1.0",
            "presentation": presentation_filename,
            "audio": audio_filename,
            "timeline": timeline_filename,
            "duration_ms": int(duration_ms),
            "slides": int(slide_count)
        }

        manifest_path = session_dir / "manifest.json"
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest_data, f, indent=2)

        logger.info(f"ManifestBuilder | Successfully built manifest to {manifest_path}")
        return manifest_path

manifest_builder = ManifestBuilder()
