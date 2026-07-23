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
async def start_bot():
    try:
        res = await meeting_bot_service.start_bot()
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/join")
async def join_meeting(req: JoinRequest):
    try:
        res = await meeting_bot_service.join_meeting(req.meeting_url, req.display_name)
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/leave")
async def leave_meeting():
    try:
        res = await meeting_bot_service.leave_meeting()
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/stop")
async def stop_bot():
    try:
        res = await meeting_bot_service.stop_bot()
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/status")
async def get_status():
    try:
        res = await meeting_bot_service.get_status()
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/participants")
async def get_participants():
    try:
        res = await meeting_bot_service.get_participants()
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/chat")
async def get_chat():
    try:
        res = await meeting_bot_service.get_chat()
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/audio/play")
async def play_audio(req: PlayAudioRequest):
    try:
        res = await meeting_bot_service.play_audio(req.audio_path)
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/audio/stop")
async def stop_audio():
    try:
        res = await meeting_bot_service.stop_audio()
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/screenshot")
async def get_screenshot(session_id: str = Query(...)):
    try:
        res = await meeting_bot_service.capture_screen(session_id)
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
