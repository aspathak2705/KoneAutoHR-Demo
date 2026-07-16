from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from typing import Dict, Any
from app.integrations.microsoft.auth import microsoft_auth_manager
from app.integrations.microsoft.graph_client import microsoft_graph_client

router = APIRouter(prefix="/microsoft", tags=["Microsoft Integration"])

@router.get("/login", response_model=Dict[str, str])
def get_login_url():
    try:
        url = microsoft_auth_manager.get_authorization_url()
        return {"auth_url": url}
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.get("/callback")
async def oauth_callback(code: str, state: str = "autohr_auth"):
    try:
        await microsoft_auth_manager.exchange_code(code)
        # Redirect back to the frontend profile configuration page
        return RedirectResponse(url="http://localhost:5173/profile?microsoft_status=success")
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.get("/profile", response_model=Dict[str, Any])
async def get_microsoft_profile():
    try:
        profile = await microsoft_graph_client.fetch_profile()
        return profile
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )

@router.post("/disconnect", status_code=status.HTTP_204_NO_CONTENT)
def disconnect_microsoft():
    microsoft_auth_manager.disconnect()
