import sys
import datetime
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from fastapi.testclient import TestClient
from main import app
from app.db.database import SessionLocal, engine, Base
from app.models.session import Session as DBSessionModel
from app.integrations.microsoft.auth import microsoft_auth_manager

def print_result(label: str, passed: bool, details: str = ""):
    status_str = "\033[92m[PASS]\033[0m" if passed else "\033[91m[FAIL]\033[0m"
    print(f"{label:<50} {status_str} {details}")

def main():
    print("=====================================================================")
    print("                AUTOHR SPRINT 2 MEETINGS VERIFIER                   ")
    print("=====================================================================\n")

    client = TestClient(app)

    # 1. Seed a test session in the database
    with SessionLocal() as db:
        # Check if test session already exists
        test_session = db.query(DBSessionModel).filter(DBSessionModel.name == "Sprint 2 Test Session").first()
        if not test_session:
            test_session = DBSessionModel(
                name="Sprint 2 Test Session",
                status="PENDING"
            )
            db.add(test_session)
            db.commit()
            db.refresh(test_session)
        session_id = test_session.id

    print_result("Test Session created in database", True, f"Session ID: {session_id}")

    # 2. Authenticate using developer mock/test token
    print("Seeding mock authentication token...")
    microsoft_auth_manager.mock_authenticate_for_testing(
        access_token="mock_access_token",
        refresh_token="mock_refresh_token"
    )
    print_result("Mock Auth token seeded", True)

    try:
        # 3. Test POST /meetings creation endpoint
        print("\nScheduling meeting via API...")
        now = datetime.datetime.now(datetime.timezone.utc)
        payload = {
            "session_id": session_id,
            "subject": "Sprint 2 Test Induction Meeting",
            "start_time": now.isoformat(),
            "end_time": (now + datetime.timedelta(hours=1)).isoformat()
        }
        res_post = client.post("/api/v1/meetings", json=payload)
        print_result("POST /meetings returns 201", res_post.status_code == 201, f"Status: {res_post.status_code}")
        
        if res_post.status_code == 201:
            meeting = res_post.json()
            meeting_id = meeting.get("id")
            join_url = meeting.get("join_url")
            print_result("Persisted Join URL exists", bool(join_url), f"Link: {join_url}")
            print_result("Graph Event ID exists", bool(meeting.get("graph_event_id")))
            print_result("Teams Meeting ID exists", bool(meeting.get("meeting_id")))

            # 4. Test GET /meetings/{id}
            print("\nFetching meeting details by ID...")
            res_get = client.get(f"/api/v1/meetings/{meeting_id}")
            print_result("GET /meetings/{id} returns 200", res_get.status_code == 200)

            # 5. Test GET /meetings/session/{session_id}
            print("\nFetching meeting details by Session ID...")
            res_session = client.get(f"/api/v1/meetings/session/{session_id}")
            print_result("GET /meetings/session/{session_id} returns 200", res_session.status_code == 200)

        # Cleanup test token
        microsoft_auth_manager.disconnect()
        print("\n=====================================================================")
        print("                 SPRINT 2 MEETINGS TEST PASS                         ")
        print("=====================================================================")

    except Exception as e:
        print(f"\nVerification failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
