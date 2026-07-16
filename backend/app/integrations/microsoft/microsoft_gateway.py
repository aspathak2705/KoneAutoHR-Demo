from app.integrations.microsoft.calendar_service import calendar_service
from app.integrations.microsoft.meeting_service import meeting_service

class MicrosoftGateway:
    """
    Unified entry point routing all application queries to Microsoft Integration Layer services.
    """
    def __init__(self):
        self.calendar = calendar_service
        self.meeting = meeting_service
        self.invitation = None
        self.user = None

microsoft_gateway = MicrosoftGateway()
