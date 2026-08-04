from fastapi import APIRouter

router = APIRouter(prefix="/voice", tags=["Voice"])

@router.get("/health")
def voice_health():
    return {"status": "ok"}
