# verify_phase2_api.py

import requests
import sys

BASE_URL = "http://127.0.0.1:8000/api/v1"

# Replace with your actual token if required
TOKEN = "autohr_master_secret_token_2026"

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
}


passed = 0
failed = 0


def check(name, response, expected=(200, 201)):
    global passed, failed

    if response.status_code in expected:
        print(f"[PASS] {name}")
        passed += 1
        return True

    print(f"[FAIL] {name}")
    print(f"Status : {response.status_code}")
    print(response.text)
    failed += 1
    return False


def main():
    print("=" * 60)
    print("AUTOHR PHASE 2 API VALIDATION")
    print("=" * 60)

    # --------------------------------------------------
    # Health
    # --------------------------------------------------
    r = requests.get(
        f"{BASE_URL}/health",
        headers=HEADERS,
    )

    if not check("Health API", r):
        sys.exit(1)

    # --------------------------------------------------
    # Create Session
    # --------------------------------------------------
    session_payload = {
        "name": "Demo Validation Session",
        "scheduled_at": "2026-07-26T10:00:00Z",
        "presentation_id": None,
        "employee_list_id": None,
    }

    r = requests.post(
        f"{BASE_URL}/sessions",
        json=session_payload,
        headers=HEADERS,
    )

    if not check("Create Session", r):
        sys.exit(1)

    session = r.json()
    session_id = session["id"]

    print(f"Session ID : {session_id}")

    # --------------------------------------------------
    # Runtime Prepare
    # --------------------------------------------------
    r = requests.post(
        f"{BASE_URL}/runtime/{session_id}/prepare",
        headers=HEADERS,
    )

    check("Prepare Runtime", r)

    # --------------------------------------------------
    # Runtime Status
    # --------------------------------------------------
    r = requests.get(
        f"{BASE_URL}/runtime/{session_id}",
        headers=HEADERS,
    )

    check("Runtime Status", r)

    if r.status_code == 200:
        runtime = r.json()

        print()
        print("Runtime State")
        print("----------------------------")

        print("State            :", runtime.get("state"))
        print("Browser State    :", runtime.get("browser_state"))
        print("Induction State  :", runtime.get("induction_state"))

    print()
    print("=" * 60)
    print(f"PASSED : {passed}")
    print(f"FAILED : {failed}")
    print("=" * 60)


if __name__ == "__main__":
    main()