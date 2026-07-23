from app.modules.semantic_browser.browser.semantic_snapshot import SemanticSnapshot
from app.modules.presentation_observer.models.observation_event import ObservationEvent
from app.modules.presentation_observer.observer.observation_context import ObservationContext
from app.modules.semantic_browser.models.presentation_state import PresentationMode
from typing import List, Tuple, Optional
import time
from loguru import logger

class ChangeDetector:
    def detect_changes(
        self, 
        curr: SemanticSnapshot, 
        context: ObservationContext
    ) -> Tuple[List[ObservationEvent], dict]:
        """
        Compares previous and current snapshot frames inside context to detect transition events.
        """
        prev = context.prev_snapshot
        events = []
        flags = {
            "presentation_started": False,
            "presentation_ended": False,
            "slide_changed": False,
            "chat_open": False,
            "participants_open": False,
            "recording_active": False
        }

        if not prev:
            if curr.presentation_state in [PresentationMode.POWERPOINT_SHARED, PresentationMode.SCREEN_SHARING]:
                events.append(ObservationEvent.PRESENTATION_STARTED)
                flags["presentation_started"] = True
                context.presentation_start_time = time.time()
            elif curr.presentation_state == PresentationMode.WAITING_SCREEN:
                events.append(ObservationEvent.WAITING)
            elif curr.presentation_state == PresentationMode.LOADING:
                events.append(ObservationEvent.LOADING)
            return events, flags

        # 1. Detect Presentation Started / Ended
        prev_active = prev.presentation_state in [PresentationMode.POWERPOINT_SHARED, PresentationMode.SCREEN_SHARING]
        curr_active = curr.presentation_state in [PresentationMode.POWERPOINT_SHARED, PresentationMode.SCREEN_SHARING]

        if not prev_active and curr_active:
            events.append(ObservationEvent.PRESENTATION_STARTED)
            flags["presentation_started"] = True
            context.presentation_start_time = time.time()
            context.last_event_timestamp = time.time()
        elif prev_active and not curr_active:
            events.append(ObservationEvent.PRESENTATION_ENDED)
            flags["presentation_ended"] = True
            context.last_event_timestamp = time.time()

        # 2. Detect Screen Share transitions
        prev_sharing = prev.presentation_state == PresentationMode.SCREEN_SHARING
        curr_sharing = curr.presentation_state == PresentationMode.SCREEN_SHARING
        if not prev_sharing and curr_sharing:
            events.append(ObservationEvent.SCREEN_SHARE_STARTED)
            context.last_event_timestamp = time.time()
        elif prev_sharing and not curr_sharing:
            events.append(ObservationEvent.SCREEN_SHARE_STOPPED)
            context.last_event_timestamp = time.time()

        # 3. Detect Chat Panel switches
        if not prev.chat_open and curr.chat_open:
            events.append(ObservationEvent.CHAT_OPENED)
            flags["chat_open"] = True
            context.last_event_timestamp = time.time()
        elif prev.chat_open and not curr.chat_open:
            events.append(ObservationEvent.CHAT_CLOSED)
            context.last_event_timestamp = time.time()

        # 4. Detect Participants List switches
        if not prev.participants_open and curr.participants_open:
            events.append(ObservationEvent.PARTICIPANTS_OPENED)
            flags["participants_open"] = True
            context.last_event_timestamp = time.time()
        elif prev.participants_open and not curr.participants_open:
            events.append(ObservationEvent.PARTICIPANTS_CLOSED)
            context.last_event_timestamp = time.time()

        # 5. Detect Recording status
        if not prev.recording_active and curr.recording_active:
            events.append(ObservationEvent.RECORDING_STARTED)
            flags["recording_active"] = True
            context.last_event_timestamp = time.time()
        elif prev.recording_active and not curr.recording_active:
            events.append(ObservationEvent.RECORDING_STOPPED)
            context.last_event_timestamp = time.time()

        # 6. Detect Slide Change via presentation_content_signature checks (no DOM heuristics)
        if curr.presentation_state == PresentationMode.POWERPOINT_SHARED:
            prev_sig = prev.presentation_content_signature if prev else None
            curr_sig = curr.presentation_content_signature
            
            # Slide change resolves if transitioning within PowerPoint and the signature shifts
            if prev and prev.presentation_state == PresentationMode.POWERPOINT_SHARED:
                if prev_sig is not None and curr_sig != prev_sig:
                    events.append(ObservationEvent.SLIDE_CHANGED)
                    flags["slide_changed"] = True
                    context.last_event_timestamp = time.time()
                    logger.info(f"ChangeDetector | SLIDE_CHANGED | Previous Signature: {prev_sig} | Current Signature: {curr_sig}")

        return events, flags

change_detector = ChangeDetector()
