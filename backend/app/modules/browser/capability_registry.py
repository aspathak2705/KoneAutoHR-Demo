from typing import Set, List
from loguru import logger

class CapabilityRegistry:
    """
    Module 6 — Capability Registry
    Stores and validates interactive capabilities supported by the active platform adapter.
    """
    def __init__(self):
        self._capabilities: Set[str] = set()

    def register_capabilities(self, capabilities: List[str]) -> None:
        for cap in capabilities:
            self._capabilities.add(cap.upper())
        logger.info(f"CapabilityRegistry | Registered platform skills: {capabilities}")

    def supports(self, capability_name: str) -> bool:
        supported = capability_name.upper() in self._capabilities
        logger.debug(f"CapabilityRegistry | Checking support for '{capability_name}': {supported}")
        return supported

capability_registry = CapabilityRegistry()
