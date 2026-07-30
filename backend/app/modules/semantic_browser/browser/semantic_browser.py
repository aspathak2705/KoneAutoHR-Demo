from playwright.async_api import Page
from app.modules.semantic_browser.browser.semantic_snapshot import SemanticSnapshot
from app.modules.semantic_browser.browser.semantic_snapshot_builder import SemanticSnapshotBuilder
from app.modules.semantic_browser.analyzers.dom_analyzer import dom_analyzer
from app.modules.semantic_browser.analyzers.accessibility_analyzer import accessibility_analyzer
from app.modules.semantic_browser.analyzers.meeting_state_analyzer import meeting_state_analyzer
from app.modules.semantic_browser.analyzers.presentation_analyzer import presentation_analyzer
from app.modules.semantic_browser.config import semantic_browser_config
from app.modules.semantic_browser.models.semantic_state import DOMSummary, AccessibilitySummary
from app.modules.semantic_browser.models.presentation_state import PresentationMode

class SemanticBrowser:
    async def generate_snapshot(self, page: Page) -> SemanticSnapshot:
        """
        Orchestrates page analyzers and passes results to the SemanticSnapshotBuilder.
        """
        # 1. DOM Scan
        dom = DOMSummary()
        if semantic_browser_config.enable_dom:
            dom = await dom_analyzer.analyze(page)
        
        # 2. Accessibility Scan
        acc = AccessibilitySummary()
        if semantic_browser_config.enable_accessibility:
            acc = await accessibility_analyzer.analyze(page)
            
        # 3. Meeting State Scan
        m_state = await meeting_state_analyzer.analyze(page, dom)
        
        # 4. Presentation Scan (accepts dom to avoid duplicate DOM queries)
        p_mode = PresentationMode.NONE
        p_sig = None
        p_details = {}
        current_slide = 0
        confidence = 0.0
        if semantic_browser_config.enable_presentation:
            p_res = await presentation_analyzer.analyze(page, dom)
            p_mode = p_res["mode"]
            p_sig = p_res.get("signature")
            p_details = p_res["details"]
            current_slide = p_res.get("current_slide", 0)
            confidence = p_res.get("confidence", 0.0)
            
        # 5. Build snapshot
        return SemanticSnapshotBuilder.build(
            meeting_state=m_state["state"],
            presentation_state=p_mode,
            dom_summary=dom,
            accessibility_summary=acc,
            chat_open=m_state["chat_open"],
            participants_open=m_state["participants_open"],
            recording_active=m_state["recording_active"],
            presentation_content_signature=p_sig,
            current_slide=current_slide,
            confidence=confidence,
            details={
                "hand_raised": m_state["hand_raised"],
                "presentation_details": p_details
            }
        )

semantic_browser = SemanticBrowser()
