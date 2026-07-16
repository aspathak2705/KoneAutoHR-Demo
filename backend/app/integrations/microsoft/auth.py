import datetime
import urllib.parse
from typing import Optional, Dict, Any
import httpx
from loguru import logger
from app.core.config import settings
from app.db.database import SessionLocal
from app.models.microsoft_token import MicrosoftToken
from app.utils.crypto import encrypt_token, decrypt_token

class MicrosoftAuthManager:
    def is_configured(self) -> bool:
        if settings.MICROSOFT_ACCESS_TOKEN:
            return True
        return bool(settings.MICROSOFT_CLIENT_ID and settings.MICROSOFT_CLIENT_SECRET)

    def get_authorization_url(self, state: str = "autohr_auth") -> str:
        if not self.is_configured():
            raise ValueError("Microsoft OAuth credentials not configured in settings.")
            
        tenant = settings.MICROSOFT_TENANT_ID or "common"
        base_url = f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/authorize"
        scopes = [
            "User.Read",
            "Calendars.ReadWrite",
            "OnlineMeetings.ReadWrite",
            "offline_access"
        ]
        params = {
            "client_id": settings.MICROSOFT_CLIENT_ID or "placeholder_client_id",
            "response_type": "code",
            "redirect_uri": settings.MICROSOFT_REDIRECT_URI,
            "response_mode": "query",
            "scope": " ".join(scopes),
            "state": state
        }
        return f"{base_url}?{urllib.parse.urlencode(params)}"

    async def exchange_code(self, code: str) -> Dict[str, Any]:
        if not self.is_configured():
            raise ValueError("Microsoft OAuth credentials not configured in settings.")
            
        tenant = settings.MICROSOFT_TENANT_ID or "common"
        url = f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"
        
        payload = {
            "client_id": settings.MICROSOFT_CLIENT_ID,
            "client_secret": settings.MICROSOFT_CLIENT_SECRET,
            "code": code,
            "redirect_uri": settings.MICROSOFT_REDIRECT_URI,
            "grant_type": "authorization_code"
        }
        
        start_time = datetime.datetime.now()
        async with httpx.AsyncClient() as client:
            response = await client.post(url, data=payload)
            duration_ms = int((datetime.datetime.now() - start_time).total_seconds() * 1000)
            
            if response.status_code >= 400:
                logger.error(f"MicrosoftAuthManager | ExchangeCode | Error: {response.text} | Duration: {duration_ms} ms")
                raise ValueError(f"OAuth code exchange failed: {response.text}")
                
            data = response.json()
            self.save_tokens(data)
            logger.info(f"MicrosoftAuthManager | ExchangeCode | Success | Duration: {duration_ms} ms")
            return data

    async def refresh_access_token(self, refresh_token: str) -> Dict[str, Any]:
        if not self.is_configured():
            raise ValueError("Microsoft OAuth credentials not configured in settings.")
            
        tenant = settings.MICROSOFT_TENANT_ID or "common"
        url = f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"
        
        payload = {
            "client_id": settings.MICROSOFT_CLIENT_ID,
            "client_secret": settings.MICROSOFT_CLIENT_SECRET,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token"
        }
        
        start_time = datetime.datetime.now()
        async with httpx.AsyncClient() as client:
            response = await client.post(url, data=payload)
            duration_ms = int((datetime.datetime.now() - start_time).total_seconds() * 1000)
            
            if response.status_code >= 400:
                logger.error(f"MicrosoftAuthManager | RefreshToken | Error: {response.text} | Duration: {duration_ms} ms")
                raise ValueError(f"OAuth token refresh failed: {response.text}")
                
            data = response.json()
            self.save_tokens(data)
            logger.info(f"MicrosoftAuthManager | RefreshToken | Success | Duration: {duration_ms} ms")
            return data

    def save_tokens(self, token_response: Dict[str, Any]):
        expires_in = token_response.get("expires_in", 3600)
        now = datetime.datetime.now()
        expires_at = now + datetime.timedelta(seconds=expires_in)
        
        access_token_plain = token_response.get("access_token")
        refresh_token_plain = token_response.get("refresh_token")
        
        if not access_token_plain or not refresh_token_plain:
            raise ValueError("Invalid token response content.")

        # Encrypt tokens
        encrypted_access = encrypt_token(access_token_plain)
        encrypted_refresh = encrypt_token(refresh_token_plain)

        with SessionLocal() as db:
            # Delete old sessions
            db.query(MicrosoftToken).delete()
            
            db_token = MicrosoftToken(
                access_token=encrypted_access,
                refresh_token=encrypted_refresh,
                expires_at=expires_at
            )
            db.add(db_token)
            db.commit()

    def get_access_token(self) -> Optional[str]:
        if settings.MICROSOFT_ACCESS_TOKEN:
            return settings.MICROSOFT_ACCESS_TOKEN

        with SessionLocal() as db:
            db_token = db.query(MicrosoftToken).first()
            if not db_token:
                return None
                
            if datetime.datetime.now() >= db_token.expires_at:
                logger.warning("MicrosoftAuthManager | GetAccessToken | Token expired in database.")
                return None
                
            # Decrypt access token
            return decrypt_token(db_token.access_token)

    def disconnect(self):
        with SessionLocal() as db:
            db.query(MicrosoftToken).delete()
            db.commit()
        logger.info("MicrosoftAuthManager | Disconnect | Session database records cleared.")

    def mock_authenticate_for_testing(self, access_token: str = "mock_access_token", refresh_token: str = "mock_refresh_token"):
        """Seed tokens directly for validation test suites without making active OAuth requests."""
        expires_at = datetime.datetime.now() + datetime.timedelta(hours=1)
        
        encrypted_access = encrypt_token(access_token)
        encrypted_refresh = encrypt_token(refresh_token)

        with SessionLocal() as db:
            db.query(MicrosoftToken).delete()
            db_token = MicrosoftToken(
                access_token=encrypted_access,
                refresh_token=encrypted_refresh,
                expires_at=expires_at
            )
            db.add(db_token)
            db.commit()

microsoft_auth_manager = MicrosoftAuthManager()
