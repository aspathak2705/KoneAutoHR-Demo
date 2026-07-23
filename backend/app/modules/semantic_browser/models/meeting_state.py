from enum import Enum

# Note: Do not confuse MeetingState with BotState.
# - MeetingState.LOBBY represents the browser DOM observing the lobby screen.
# - BotState.WAITING represents the bot lifecycle state waiting for admission.

class MeetingState(str, Enum):
    LOBBY = "LOBBY"
    CONNECTING = "CONNECTING"
    CONNECTED = "CONNECTED"
    DISCONNECTED = "DISCONNECTED"
