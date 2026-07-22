from typing import Optional, Dict
from sqlalchemy.orm import Session as DBSession
from loguru import logger
from app.modules.assets.asset_registry import asset_registry
from app.modules.assets.asset_cache import asset_cache
from app.modules.assets.storage_provider import StorageProvider, LocalStorageProvider

class AssetManager:
    """
    Module 1 — Asset Manager
    Central authority for resolving, loading, caching, and serving presentation assets.
    Decoupled from absolute file paths.
    """
    def __init__(self):
        self._providers: Dict[str, StorageProvider] = {
            "LOCAL": LocalStorageProvider()
        }

    def register_provider(self, name: str, provider: StorageProvider) -> None:
        self._providers[name.upper()] = provider
        logger.info(f"AssetManager | Registered storage provider '{name.upper()}'")

    def resolve(self, db: DBSession, asset_id: str) -> str:
        """
        Resolves asset ID into a valid local file path.
        """
        # 1. Check local cache first
        cached = asset_cache.get(asset_id)
        if cached:
            return cached

        # 2. Lookup registry
        meta = asset_registry.get_asset(db, asset_id)
        if not meta:
            # Check if asset_id is already a valid local path (fallback/dev mode)
            import os
            if os.path.exists(asset_id):
                return asset_id
            raise FileNotFoundError(f"AssetManager | Asset ID {asset_id} is not registered.")

        # 3. Resolve using registered storage driver
        provider = self._providers.get(meta.storage_provider.upper())
        if not provider:
            raise NotImplementedError(f"AssetManager | Storage provider {meta.storage_provider} is not registered.")

        local_path = provider.resolve_local_path(meta.storage_uri)
        asset_cache.put(asset_id, local_path)
        return local_path

asset_manager = AssetManager()
