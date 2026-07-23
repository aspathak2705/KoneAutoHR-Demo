import hashlib
import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session as DBSession
from app.modules.induction.package.storage_provider import storage_provider
from app.repositories.presentation_asset_repository import presentation_asset_repository
from app.models.presentation_asset import PresentationAsset

class AssetManager:
    def compute_md5(self, data: bytes) -> str:
        return hashlib.md5(data).hexdigest()

    def generate_metadata(self, filename: str, content: bytes, relative_path: str) -> dict:
        """
        Generates detailed metadata for a file.
        """
        suffix = Path(filename).suffix.lstrip('.').lower()
        return {
            "filename": filename,
            "size_bytes": len(content),
            "file_extension": suffix,
            "relative_path": relative_path,
            "registered_at": datetime.datetime.now().isoformat(),
            "mime_type": f"application/{suffix}" if suffix not in ["mp3", "wav", "png", "jpg", "mp4"] else f"{'audio' if suffix in ['mp3', 'wav'] else 'image' if suffix in ['png', 'jpg'] else 'video'}/{suffix}"
        }

    def save_and_register_asset(
        self,
        db: DBSession,
        presentation_id: str,
        relative_path: str,
        content: bytes,
        asset_type: str,
    ) -> PresentationAsset:
        """
        Saves file content via storage provider and registers it in database as a PresentationAsset.
        Handles versioning dynamically (increments version if different hash found).
        """
        # 1. Compute integrity hash
        checksum = self.compute_md5(content)

        # 2. Check for existing versioning
        existing_assets = presentation_asset_repository.get_all_by_presentation(db, presentation_id)
        version = 1
        for asset in existing_assets:
            if asset.storage_uri.endswith(relative_path):
                if asset.checksum == checksum:
                    # Return exact match
                    return asset
                else:
                    # Increment version for modification
                    version = (asset.version or 1) + 1

        # 3. Save via Storage Provider (Storage abstraction)
        storage_uri = storage_provider.save_file(relative_path, content)

        # 4. Create db record
        asset = presentation_asset_repository.create(
            db=db,
            presentation_id=presentation_id,
            asset_type=asset_type,
            storage_uri=storage_uri,
            storage_provider="LOCAL",
            checksum=checksum,
            version=version
        )
        return asset

    def delete_asset(self, db: DBSession, asset_id: str) -> None:
        asset = presentation_asset_repository.get(db, asset_id)
        if asset:
            path = Path(asset.storage_uri)
            try:
                storage_provider.delete_file(path.name)
            except Exception:
                pass
            presentation_asset_repository.delete(db, asset.id)

asset_manager = AssetManager()
