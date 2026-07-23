from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession
from typing import List, Optional
from app.models.presentation_asset import PresentationAsset

class PresentationAssetRepository:
    def get(self, db: DBSession, id: str) -> Optional[PresentationAsset]:
        stmt = select(PresentationAsset).where(PresentationAsset.id == id)
        return db.scalars(stmt).first()

    def get_by_presentation(self, db: DBSession, presentation_id: str) -> List[PresentationAsset]:
        stmt = select(PresentationAsset).where(PresentationAsset.presentation_id == presentation_id)
        return list(db.scalars(stmt).all())

    def get_by_type(self, db: DBSession, presentation_id: str, asset_type: str) -> List[PresentationAsset]:
        stmt = select(PresentationAsset).where(
            PresentationAsset.presentation_id == presentation_id,
            PresentationAsset.asset_type == asset_type
        )
        return list(db.scalars(stmt).all())

    def create(
        self,
        db: DBSession,
        presentation_id: str,
        asset_type: str,
        storage_uri: str,
        storage_provider: str = "LOCAL",
        checksum: Optional[str] = None,
        version: int = 1
    ) -> PresentationAsset:
        db_obj = PresentationAsset(
            presentation_id=presentation_id,
            asset_type=asset_type,
            storage_uri=storage_uri,
            storage_provider=storage_provider,
            checksum=checksum,
            version=version
        )
        db.add(db_obj)
        db.flush()
        return db_obj

    def delete(self, db: DBSession, id: str) -> Optional[PresentationAsset]:
        db_obj = self.get(db, id)
        if db_obj:
            db.delete(db_obj)
            db.flush()
        return db_obj

presentation_asset_repository = PresentationAssetRepository()
