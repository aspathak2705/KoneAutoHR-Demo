from enum import Enum

class MeetingState(str, Enum):
    LOBBY = "LOBBY"
    CONNECTING = "CONNECTING"
    CONNECTED = "CONNECTED"
    DISCONNECTED = "DISCONNECTED"
