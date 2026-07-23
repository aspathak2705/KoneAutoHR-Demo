from playwright.async_api import Page
from app.modules.semantic_browser.models.semantic_state import DOMSummary, DOMElementSummary
from loguru import logger

class DOMAnalyzer:
    async def analyze(self, page: Page) -> DOMSummary:
        """
        Scrapes visible interactive elements, forms, modals, dialogs, regions, and panels from DOM.
        """
        logger.debug("DOMAnalyzer | Scanning visible DOM elements and regions...")
        
        # Expanded selectors list to capture regions, forms, dialogs, and panels
        selectors = (
            "button, input, select, textarea, [role='button'], [role='tab'], [role='menuitem'], "
            "[role='dialog'], form, [role='region'], [role='panel'], [role='alert']"
        )
        
        elements = []
        try:
            locators = page.locator(selectors)
            count = await locators.count()
            
            for i in range(count):
                loc = locators.nth(i)
                if not await loc.is_visible():
                    continue
                    
                tag = await loc.evaluate("el => el.tagName.toLowerCase()")
                el_id = await loc.get_attribute("id") or None
                role = await loc.get_attribute("role") or None
                label = await loc.get_attribute("aria-label") or await loc.get_attribute("title") or None
                text = await loc.inner_text() or None
                
                if text and len(text) > 60:
                    text = text[:57] + "..."
                    
                bbox = await loc.bounding_box()
                bbox_dict = None
                if bbox:
                    bbox_dict = {
                        "x": bbox["x"],
                        "y": bbox["y"],
                        "width": bbox["width"],
                        "height": bbox["height"]
                    }
                    
                elements.append(DOMElementSummary(
                    tag=tag,
                    id=el_id,
                    role=role,
                    label=label,
                    text=text,
                    is_visible=True,
                    bounding_box=bbox_dict
                ))
        except Exception as e:
            logger.error(f"DOMAnalyzer | Error scanning DOM elements: {e}")

        return DOMSummary(
            elements=elements,
            total_interactive_count=len(elements)
        )

dom_analyzer = DOMAnalyzer()
