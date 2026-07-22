from typing import Dict, Any, List
from playwright.async_api import Page
from app.modules.browser.dom_processor import dom_processor
from app.modules.browser.accessibility_processor import accessibility_processor

class PerceptionEngine:
    """
    Module 3 — Perception Engine
    Collects raw DOM nodes and Accessibility summaries.
    Returns: { "page": "Teams pre-join", "buttons": [...], "inputs": [...] }
    """
    async def perceive(self, page: Page) -> Dict[str, Any]:
        url = page.url
        title = await page.title()
        
        elements = await dom_processor.get_interactive_elements(page)
        
        # Classify buttons and text inputs
        buttons = []
        inputs = []
        
        for el in elements:
            label = el["aria_label"] or el["text"] or el["id"]
            if el["tag"] == "button" or el["tag"] == "a" or el["aria_label"]:
                if label:
                    buttons.append(label)
            elif el["tag"] == "input":
                inputs.append(el["placeholder"] or el["id"] or "text_input")

        return {
            "url": url,
            "title": title,
            "buttons": list(set(buttons)),
            "inputs": list(set(inputs)),
            "elements": elements
        }

perception_engine = PerceptionEngine()
