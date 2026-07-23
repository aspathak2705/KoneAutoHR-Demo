import json
from pathlib import Path
from sqlalchemy.orm import Session as DBSession
from app.modules.induction.package.asset_manager import asset_manager

class AssetPipeline:
    def execute(
        self,
        db: DBSession,
        presentation_id: str,
        session_id: str,
        audio_tracks: list,
        session_dir: Path
    ) -> dict:
        """
        Takes synthesized audio track files, registers them in the database as assets,
        and generates audio_manifest.json.
        """
        manifest_tracks = []

        for track in audio_tracks:
            file_path = Path(track["file_path"])
            if file_path.exists():
                with open(file_path, "rb") as f:
                    content = f.read()

                # Register in database via AssetManager
                relative_path = f"sessions/{session_id}/audio/{track['filename']}"
                asset = asset_manager.save_and_register_asset(
                    db=db,
                    presentation_id=presentation_id,
                    relative_path=relative_path,
                    content=content,
                    asset_type="audio"
                )

                # Generate detailed metadata
                metadata = asset_manager.generate_metadata(track["filename"], content, relative_path)
                
                manifest_tracks.append({
                    "label": track["label"],
                    "slide_number": track["slide_number"],
                    "filename": track["filename"],
                    "duration": track["duration"],
                    "checksum": asset.checksum,
                    "version": asset.version,
                    "path": relative_path,
                    "voice": track["voice"],
                    "metadata": metadata
                })

        manifest_data = {
            "session_id": session_id,
            "presentation_id": presentation_id,
            "total_audio_tracks": len(manifest_tracks),
            "tracks": manifest_tracks
        }

        # Write audio_manifest.json
        manifest_path = session_dir / "audio_manifest.json"
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest_data, f, indent=2)

        return manifest_data

asset_pipeline = AssetPipeline()
