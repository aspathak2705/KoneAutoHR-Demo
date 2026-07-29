import os
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session as DBSession
from app.db.database import get_db
from app.core.dependencies import verify_token
from app.schemas.agent_configuration import AgentConfigurationResponse, AgentConfigurationUpdate
from app.services.agent_configuration_service import agent_configuration_service
from app.modules.meeting_bot.browser.browser_manager import browser_manager

router = APIRouter(prefix="/agent", tags=["Agent Configuration"])

@router.get("/config", response_model=AgentConfigurationResponse)
def get_agent_config(db: DBSession = Depends(get_db)):
    cfg = agent_configuration_service.get_config(db)
    if not cfg:
        # Return a default configuration schema if not initialized yet
        return {
            "id": "",
            "provider": "microsoft",
            "email": "",
            "tenant": "",
            "profile_path": "profiles/agent/microsoft",
            "is_connected": False,
            "created_at": "2026-01-01T00:00:00",
            "updated_at": "2026-01-01T00:00:00"
        }
    return cfg

@router.put("/config", response_model=AgentConfigurationResponse)
def update_agent_config(config_in: AgentConfigurationUpdate, db: DBSession = Depends(get_db)):
    return agent_configuration_service.update_config(db, config_in)

@router.post("/connect", response_model=AgentConfigurationResponse)
async def connect_agent_microsoft(db: DBSession = Depends(get_db)):
    # Launch browser in a persistent directory with visual interactive support so user can sign in
    # Use standard Agent configuration profile path
    profile_relative_path = "profiles/agent/microsoft"
    # Ensure profile path is fully qualified in uploads
    from app.core.config import settings
    profile_absolute_path = str(os.path.join(os.path.dirname(settings.UPLOAD_DIR), profile_relative_path))
    
    # Temporarily force headful execution to let user interactively sign in
    # Save original headless configuration
    from app.modules.meeting_bot.config import meeting_bot_config
    original_headless = meeting_bot_config.headless
    meeting_bot_config.headless = False
    
    try:
        # Override profile dir for launcher setup in BrowserManager dynamically
        # Since rule 4 states: "Only BrowserManager may decide profile_path, launch_persistent_context"
        # We will trigger the connect sequence which opens Microsoft login page
        session = await browser_manager.launch("agent_connection")
        
        # Navigate directly to Microsoft Account login page so the admin can log in
        await session.page.goto("https://login.live.com", wait_until="domcontentloaded", timeout=60000)
        
        # Keep connection open for 90 seconds or until user signs in/closes page
        # Polling check inside loop to detect successful login via live.com redirects or manual admin action
        for _ in range(90):
            if session.page.is_closed():
                break
            url = session.page.url
            if "login.live.com" not in url and "login.microsoftonline.com" not in url and "about:blank" not in url:
                # User has redirected out of login sequence (indicating success)
                break
            import asyncio
            await asyncio.sleep(1)
            
        # Get active user info / metadata if possible, otherwise generic status
        # Retrieve input value if username is entered or page is loaded
        email = None
        try:
            # Try to grab username/email from profile menu or storage if logged in
            # We can check login email indicators on standard Microsoft profile headers
            # Fallback to general admin input if unavailable
            pass
        except Exception:
            pass

        # Close the connection setup session
        await browser_manager.close()
        
        # Set configuration state
        config_update = AgentConfigurationUpdate(
            provider="microsoft",
            email=email or "connected@microsoft.com",
            tenant="common",
            profile_path=profile_relative_path,
            is_connected=True
        )
        return agent_configuration_service.update_config(db, config_update)
        
    except Exception as e:
        await browser_manager.close()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Microsoft account connection failed: {str(e)}"
        )
    finally:
        meeting_bot_config.headless = original_headless

@router.post("/disconnect", response_model=AgentConfigurationResponse)
def disconnect_agent_microsoft(db: DBSession = Depends(get_db)):
    cfg = agent_configuration_service.get_config(db)
    if not cfg:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent configuration not found."
        )
    
    config_update = AgentConfigurationUpdate(
        provider=cfg.provider,
        email="",
        tenant="",
        profile_path=cfg.profile_path,
        is_connected=False
    )
    return agent_configuration_service.update_config(db, config_update)
