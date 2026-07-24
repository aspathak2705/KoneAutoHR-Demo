from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional
from app.modules.meeting_bot.services.meeting_bot_service import meeting_bot_service

router = APIRouter(prefix="/meeting-bot", tags=["Meeting Bot"])

class JoinRequest(BaseModel):
    meeting_url: str
    display_name: Optional[str] = "KONE AI Bot"

class PlayAudioRequest(BaseModel):
    audio_path: str

@router.post("/start")
async def start_bot(session_id: str = "default_session"):
    try:
        res = await meeting_bot_service.start_bot(session_id)
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/join")
async def join_meeting(req: JoinRequest, session_id: str = "default_session"):
    try:
        res = await meeting_bot_service.join_meeting(req.meeting_url, req.display_name, session_id)
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/leave")
async def leave_meeting(session_id: str = "default_session"):
    try:
        res = await meeting_bot_service.leave_meeting(session_id)
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/stop")
async def stop_bot(session_id: str = "default_session"):
    try:
        res = await meeting_bot_service.stop_bot(session_id)
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/status")
async def get_status(session_id: str = "default_session"):
    try:
        res = await meeting_bot_service.get_status(session_id)
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/participants")
async def get_participants(session_id: str = "default_session"):
    try:
        res = await meeting_bot_service.get_participants(session_id)
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/chat")
async def get_chat(session_id: str = "default_session"):
    try:
        res = await meeting_bot_service.get_chat(session_id)
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/play-audio")
async def play_audio(req: PlayAudioRequest, session_id: str = "default_session"):
    try:
        res = await meeting_bot_service.play_audio(req.audio_path, session_id)
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/stop-audio")
async def stop_audio(session_id: str = "default_session"):
    try:
        res = await meeting_bot_service.stop_audio(session_id)
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
