from playwright.async_api import Page
from app.modules.semantic_browser.models.semantic_state import AccessibilitySummary, AccessibilityNode
from loguru import logger

class AccessibilityAnalyzer:
    async def analyze(self, page: Page) -> AccessibilitySummary:
        """
        Retrieves the Playwright accessibility tree snapshot and flattens it.
        """
        logger.debug("AccessibilityAnalyzer | Fetching accessibility tree snapshot...")
        nodes = []
        focused_el = None
        
        try:
            snapshot = await page.accessibility.snapshot()
            if snapshot:
                self._flatten_node(snapshot, nodes)
                
            # Find the focused element if any
            for n in nodes:
                if n.focused:
                    focused_el = n
                    break
        except Exception as e:
            logger.error(f"AccessibilityAnalyzer | Failed to capture accessibility tree: {e}")

        return AccessibilitySummary(
            nodes=nodes,
            focused_element=focused_el
        )

    def _flatten_node(self, node: dict, nodes_list: list) -> None:
        role = node.get("role", "unknown")
        name = node.get("name")
        description = node.get("description")
        focused = node.get("focused", False)
        
        # Add to list
        nodes_list.append(AccessibilityNode(
            role=role,
            name=name,
            description=description,
            focused=focused
        ))
        
        # Recursively process children
        children = node.get("children", [])
        for child in children:
            self._flatten_node(child, nodes_list)

accessibility_analyzer = AccessibilityAnalyzer()
