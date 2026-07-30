from playwright.async_api import Page
from app.modules.semantic_browser.models.semantic_state import AccessibilitySummary, AccessibilityNode
from loguru import logger

class AccessibilityAnalyzer:
    async def analyze(self, page: Page) -> AccessibilitySummary:
        """
        Retrieves the Playwright accessibility tree snapshot and flattens it.
        Supports fallback via CDP AXTree commands for newer Playwright versions.
        """
        if page.is_closed():
            return AccessibilitySummary(nodes=[], focused_element=None)

        logger.debug("AccessibilityAnalyzer | Fetching accessibility tree snapshot...")
        nodes = []
        focused_el = None
        
        try:
            # Check if standard page.accessibility property exists
            if hasattr(page, "accessibility") and page.accessibility is not None:
                snapshot = await page.accessibility.snapshot()
                if snapshot:
                    self._flatten_node(snapshot, nodes)
            else:
                # Fallback to Chrome DevTools Protocol to query AXTree directly
                logger.debug("AccessibilityAnalyzer | Using CDP fallback to fetch accessibility tree...")
                client = await page.context.new_cdp_session(page)
                res = await client.send("Accessibility.getFullAXTree")
                ax_nodes = res.get("nodes", [])
                for node in ax_nodes:
                    role_val = node.get("role", {}).get("value", "unknown")
                    name_val = node.get("name", {}).get("value")
                    desc_val = node.get("description", {}).get("value")
                    
                    # Resolve focus status
                    focused = False
                    for prop in node.get("properties", []):
                        if prop.get("name") == "focused":
                            focused = prop.get("value", {}).get("value", False)
                            break
                            
                    nodes.append(AccessibilityNode(
                        role=str(role_val),
                        name=str(name_val) if name_val is not None else None,
                        description=str(desc_val) if desc_val is not None else None,
                        focused=bool(focused)
                    ))
                # Close CDP session cleanly
                await client.detach()
                
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
        
        nodes_list.append(AccessibilityNode(
            role=role,
            name=name,
            description=description,
            focused=focused
        ))
        
        children = node.get("children", [])
        for child in children:
            self._flatten_node(child, nodes_list)

accessibility_analyzer = AccessibilityAnalyzer()
