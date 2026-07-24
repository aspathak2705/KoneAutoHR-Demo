from fastapi import APIRouter, HTTPException
from app.modules.presentation_observer.services.presentation_observer_service import presentation_observer_service
from app.modules.presentation_observer.models.observation import Observation
from loguru import logger

router = APIRouter()

@router.get("/observation", response_model=Observation)
async def get_observation(session_id: str = "default_session"):
    try:
        obs = presentation_observer_service.get_latest_observation(session_id)
        if not obs:
            # If no cached observation, run a cycle dynamically to populate
            obs = await presentation_observer_service.run_observation_cycle(session_id)
        return obs
    except ValueError as ve:
        logger.warning(f"Observer API | Observation skipped: {ve}")
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.exception("Observer API | Error fetching observation.")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/state")
async def get_state(session_id: str = "default_session"):
    obs = presentation_observer_service.get_latest_observation(session_id)
    if not obs:
        try:
            obs = await presentation_observer_service.run_observation_cycle(session_id)
        except ValueError as ve:
            raise HTTPException(status_code=400, detail=str(ve))
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
            
    return {
        "current_state": obs.current_state.value,
        "slide_changed": obs.slide_changed,
        "presentation_started": obs.presentation_started,
        "presentation_ended": obs.presentation_ended,
        "timeline_index": obs.timeline_index
    }

@router.get("/timeline")
def get_timeline(session_id: str = "default_session"):
    return {
        "timeline": [evt.value for evt in presentation_observer_service.get_timeline(session_id)]
    }

@router.get("/events")
async def get_events(session_id: str = "default_session"):
    obs = presentation_observer_service.get_latest_observation(session_id)
    if not obs:
        return {"events": []}
    return {
        "events": [evt.value for evt in obs.events]
    }
