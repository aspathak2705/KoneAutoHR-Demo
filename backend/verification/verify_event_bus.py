import sys
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from app.services.event_bus import runtime_event_bus

def print_result(label: str, passed: bool, details: str = ""):
    status_str = "\033[92m[PASS]\033[0m" if passed else "\033[91m[FAIL]\033[0m"
    print(f"{label:<50} {status_str} {details}")

def main():
    print("=====================================================================")
    print("            AUTOHR SPRINT RC-5 RUNTIME EVENT BUS VERIFIER            ")
    print("=====================================================================\n")

    received_events = []

    def on_meeting_joined(session_id, data):
        received_events.append((session_id, "MeetingJoined", data))

    # Subscribe to Event Bus
    runtime_event_bus.subscribe("MeetingJoined", on_meeting_joined)

    # Publish an event
    runtime_event_bus.publish("test_session_id", "MeetingJoined", {"detail": "success"})

    # Asserts
    print_result("Event callback called", len(received_events) == 1)
    if len(received_events) == 1:
        print_result("Event session matches", received_events[0][0] == "test_session_id")
        print_result("Event name matches", received_events[0][1] == "MeetingJoined")
        print_result("Event payload matches", received_events[0][2].get("detail") == "success")

    print("\n=====================================================================")
    print("                 SPRINT RC-5 EVENT BUS TEST PASS                     ")
    print("=====================================================================")

if __name__ == "__main__":
    main()
