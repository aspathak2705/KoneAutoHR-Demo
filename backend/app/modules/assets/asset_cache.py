import os
from typing import Dict, Optional
from loguru import logger

class AssetCache:
    def __init__(self):
        self._cache: Dict[str, str] = {}

    def get(self, asset_id: str) -> Optional[str]:
        path = self._cache.get(asset_id)
        if path and os.path.exists(path):
            return path
        return None

    def put(self, asset_id: str, path: str) -> None:
        self._cache[asset_id] = path
        logger.debug(f"AssetCache | Cached asset {asset_id} -> {path}")

    def clear(self) -> None:
        self._cache.clear()

asset_cache = AssetCache()
