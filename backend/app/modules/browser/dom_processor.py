from typing import List, Dict, Any
from playwright.async_api import Page

class DOMProcessor:
    """
    Parses and filters raw DOM structures to find interactive inputs, buttons, and text fields.
    """
    async def get_interactive_elements(self, page: Page) -> List[Dict[str, Any]]:
        # Evaluate selector-based interactive elements on page context
        elements = []
        try:
            # Query standard clickable or input selectors
            locators = await page.locator("button, a, input, [role='button']").all()
            for index, loc in enumerate(locators):
                try:
                    text = await loc.inner_text()
                    aria_label = await loc.get_attribute("aria-label")
                    placeholder = await loc.get_attribute("placeholder")
                    element_id = await loc.get_attribute("id")
                    tag_name = await loc.evaluate("el => el.tagName")
                    
                    elements.append({
                        "index": index,
                        "tag": tag_name.lower() if tag_name else "element",
                        "text": text.strip() if text else "",
                        "aria_label": aria_label if aria_label else "",
                        "placeholder": placeholder if placeholder else "",
                        "id": element_id if element_id else "",
                        "locator": loc
                    })
                except Exception:
                    continue
        except Exception:
            pass
        return elements

dom_processor = DOMProcessor()
