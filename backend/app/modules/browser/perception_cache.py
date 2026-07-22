from typing import Dict, Any, Optional
from loguru import logger

class PerceptionCache:
    """
    Module 9 — Perception Cache
    Caches parsed tree signatures to optimize processing cycles and reduce CPU/parsing overhead.
    """
    def __init__(self):
        self._cached_signature: Optional[str] = None
        self._cached_perception: Optional[Dict[str, Any]] = None

    def get(self, signature: str) -> Optional[Dict[str, Any]]:
        if self._cached_signature == signature:
            logger.debug("PerceptionCache | HIT - returned cached DOM outline.")
            return self._cached_perception
        return None

    def put(self, signature: str, perception: Dict[str, Any]) -> None:
        self._cached_signature = signature
        self._cached_perception = perception
        logger.debug(f"PerceptionCache | MISS - cached new signature: {signature[:30]}")

    def invalidate(self) -> None:
        self._cached_signature = None
        self._cached_perception = None

perception_cache = PerceptionCache()
