import datetime
import httpx
from loguru import logger
from app.integrations.microsoft.auth import microsoft_auth_manager

class CalendarService:
    async def create_event(
        self,
        subject: str,
        start_time: datetime.datetime,
        end_time: datetime.datetime,
        body_content: str
    ) -> dict:
        token = microsoft_auth_manager.get_access_token()
        if token == "mock_access_token":
            return {
                "id": "mock-graph-event-id",
                "subject": subject,
                "start": {"dateTime": start_time.isoformat()},
                "end": {"dateTime": end_time.isoformat()}
            }
        
        if not token:
            raise ValueError("Microsoft Auth: Active token missing. Please authenticate.")
            
        url = "https://graph.microsoft.com/v1.0/me/events"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "subject": subject,
            "body": {
                "contentType": "HTML",
                "content": body_content
            },
            "start": {
                "dateTime": start_time.strftime("%Y-%m-%dT%H:%M:%S"),
                "timeZone": "UTC"
            },
            "end": {
                "dateTime": end_time.strftime("%Y-%m-%dT%H:%M:%S"),
                "timeZone": "UTC"
            }
        }
        
        start_time_log = datetime.datetime.now()
        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=headers, json=payload)
            duration_ms = int((datetime.datetime.now() - start_time_log).total_seconds() * 1000)
            
            if response.status_code >= 400:
                logger.error(f"CalendarService | CreateEvent | Error: {response.text} | Duration: {duration_ms} ms")
                raise ValueError(f"Calendar event creation failed: {response.text}")
                
            logger.info(f"CalendarService | CreateEvent | Success | Duration: {duration_ms} ms")
            return response.json()

calendar_service = CalendarService()
