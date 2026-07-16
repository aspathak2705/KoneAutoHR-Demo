import datetime
from typing import Dict, Any, Optional
import httpx
from loguru import logger
from app.integrations.microsoft.auth import microsoft_auth_manager

class MicrosoftGraphClient:
    def __init__(self):
        self.base_url = "https://graph.microsoft.com/v1.0"

    def _get_headers(self) -> Dict[str, str]:
        token = microsoft_auth_manager.get_access_token()
        if not token:
            raise ValueError("Microsoft Integration Layer: Access token missing or expired. Please authenticate.")
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

    async def fetch_profile(self) -> Dict[str, Any]:
        # Handle mock authentication for integration tests
        token = microsoft_auth_manager.get_access_token()
        if token == "mock_access_token":
            return {
                "displayName": "Mock HR Admin User",
                "mail": "hr@kone.com",
                "id": "mock-graph-user-id"
            }

        headers = self._get_headers()
        url = f"{self.base_url}/me"
        
        start_time = datetime.datetime.now()
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers)
            duration_ms = int((datetime.datetime.now() - start_time).total_seconds() * 1000)
            
            if response.status_code >= 400:
                logger.error(f"MicrosoftGraphClient | FetchProfile | Error: {response.text} | Duration: {duration_ms} ms")
                raise ValueError(f"Failed to retrieve Microsoft profile: {response.text}")
                
            data = response.json()
            logger.info(f"MicrosoftGraphClient | FetchProfile | Success | Duration: {duration_ms} ms")
            return {
                "displayName": data.get("displayName"),
                "mail": data.get("mail") or data.get("userPrincipalName"),
                "id": data.get("id")
            }

microsoft_graph_client = MicrosoftGraphClient()
