import datetime
import httpx
from loguru import logger
from app.integrations.microsoft.auth import microsoft_auth_manager

class MeetingService:
    async def create_online_meeting(
        self,
        subject: str,
        start_time: datetime.datetime,
        end_time: datetime.datetime
    ) -> dict:
        token = microsoft_auth_manager.get_access_token()
        if token == "mock_access_token":
            return {
                "id": "mock-teams-meeting-id",
                "joinWebUrl": "https://teams.microsoft.com/l/meetup-join/mock-join-url",
                "subject": subject
            }
            
        if not token:
            raise ValueError("Microsoft Auth: Active token missing. Please authenticate.")
            
        url = "https://graph.microsoft.com/v1.0/me/onlineMeetings"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "startDateTime": start_time.strftime("%Y-%m-%dT%H:%M:%S"),
            "endDateTime": end_time.strftime("%Y-%m-%dT%H:%M:%S"),
            "subject": subject
        }
        
        start_time_log = datetime.datetime.now()
        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=headers, json=payload)
            duration_ms = int((datetime.datetime.now() - start_time_log).total_seconds() * 1000)
            
            if response.status_code >= 400:
                logger.error(f"MeetingService | CreateOnlineMeeting | Error: {response.text} | Duration: {duration_ms} ms")
                raise ValueError(f"Online meeting creation failed: {response.text}")
                
            logger.info(f"MeetingService | CreateOnlineMeeting | Success | Duration: {duration_ms} ms")
            return response.json()

meeting_service = MeetingService()
