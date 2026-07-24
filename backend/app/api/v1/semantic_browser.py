from fastapi import APIRouter, HTTPException
from app.modules.semantic_browser.services.semantic_browser_service import semantic_browser_service
from app.modules.semantic_browser.browser.semantic_snapshot import SemanticSnapshot
from app.modules.semantic_browser.models.meeting_state import MeetingState
from app.modules.semantic_browser.models.presentation_state import PresentationMode
from loguru import logger

router = APIRouter()

@router.get("/snapshot", response_model=SemanticSnapshot)
async def get_snapshot(session_id: str = "default_session"):
    try:
        return await semantic_browser_service.get_snapshot(session_id)
    except ValueError as ve:
        logger.warning(f"Semantic API | Snapshot fetch skipped: {ve}")
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.exception("Semantic API | Error generating snapshot.")
        raise HTTPException(status_code=500, detail=f"Failed to generate snapshot: {str(e)}")

@router.get("/meeting")
async def get_meeting(session_id: str = "default_session"):
    try:
        state = await semantic_browser_service.get_meeting_state(session_id)
        return {"meeting_state": state.value}
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/presentation")
async def get_presentation(session_id: str = "default_session"):
    try:
        mode = await semantic_browser_service.get_presentation_state(session_id)
        return {"presentation_mode": mode.value}
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/state")
async def get_state(session_id: str = "default_session"):
    try:
        snap = await semantic_browser_service.get_snapshot(session_id)
        return {
            "meeting_state": snap.meeting_state.value,
            "presentation_state": snap.presentation_state.value,
            "chat_open": snap.chat_open,
            "participants_open": snap.participants_open,
            "recording_active": snap.recording_active,
            "interactive_elements_count": len(snap.dom_summary.elements),
            "accessibility_nodes_count": len(snap.accessibility_summary.nodes)
        }
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
