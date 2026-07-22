from typing import Optional, List
from sqlalchemy.orm import Session as DBSession
from app.models.presentation_asset import PresentationAsset
from app.modules.assets.asset_models import AssetMetadata

class AssetRegistry:
    def get_asset(self, db: DBSession, asset_id: str) -> Optional[AssetMetadata]:
        asset = db.query(PresentationAsset).filter(PresentationAsset.id == asset_id).first()
        if not asset:
            return None
        return AssetMetadata(
            asset_id=asset.id,
            presentation_id=asset.presentation_id,
            asset_type=asset.asset_type,
            storage_provider=asset.storage_provider,
            storage_uri=asset.storage_uri,
            checksum=asset.checksum,
            version=asset.version
        )

    def get_presentation_assets(self, db: DBSession, presentation_id: str) -> List[AssetMetadata]:
        assets = db.query(PresentationAsset).filter(PresentationAsset.presentation_id == presentation_id).all()
        return [
            AssetMetadata(
                asset_id=asset.id,
                presentation_id=asset.presentation_id,
                asset_type=asset.asset_type,
                storage_provider=asset.storage_provider,
                storage_uri=asset.storage_uri,
                checksum=asset.checksum,
                version=asset.version
            ) for asset in assets
        ]

    def register_asset(
        self,
        db: DBSession,
        presentation_id: str,
        asset_type: str,
        storage_uri: str,
        storage_provider: str = "LOCAL",
        checksum: Optional[str] = None
    ) -> AssetMetadata:
        # Check if asset already exists for this presentation and URI
        asset = db.query(PresentationAsset).filter(
            PresentationAsset.presentation_id == presentation_id,
            PresentationAsset.storage_uri == storage_uri
        ).first()

        if not asset:
            asset = PresentationAsset(
                presentation_id=presentation_id,
                asset_type=asset_type,
                storage_provider=storage_provider,
                storage_uri=storage_uri,
                checksum=checksum
            )
            db.add(asset)
        else:
            asset.asset_type = asset_type
            asset.storage_provider = storage_provider
            asset.checksum = checksum
            asset.version += 1

        db.commit()
        db.refresh(asset)

        return AssetMetadata(
            asset_id=asset.id,
            presentation_id=asset.presentation_id,
            asset_type=asset.asset_type,
            storage_provider=asset.storage_provider,
            storage_uri=asset.storage_uri,
            checksum=asset.checksum,
            version=asset.version
        )

asset_registry = AssetRegistry()
