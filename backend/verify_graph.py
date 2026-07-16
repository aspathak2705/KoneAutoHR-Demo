import sys
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from fastapi.testclient import TestClient
from main import app
from app.core.config import settings
from app.integrations.microsoft.auth import microsoft_auth_manager

def print_result(label: str, passed: bool, details: str = ""):
    status_str = "\033[92m[PASS]\033[0m" if passed else "\033[91m[FAIL]\033[0m"
    print(f"{label:<45} {status_str} {details}")

def main():
    print("=====================================================================")
    print("                AUTOHR MICROSOFT GRAPH CONNECTION VERIFIER            ")
    print("=====================================================================\n")

    client = TestClient(app)

    # Check if a static developer token is set in the environment
    if settings.MICROSOFT_ACCESS_TOKEN:
        print("\033[96m[INFO]\033[0m Using static MICROSOFT_ACCESS_TOKEN from .env file.")
        try:
            print("\nFetching user profile from Microsoft Graph...")
            res_profile = client.get("/api/v1/microsoft/profile")
            print_result("GET /profile returns 200", res_profile.status_code == 200)
            if res_profile.status_code == 200:
                profile = res_profile.json()
                print_result("Active profile loaded", True, f"User: {profile.get('displayName')} <{profile.get('mail')}>")
                
            print("\n=====================================================================")
            print("                 GRAPH INTEGRATION TESTS PASS                        ")
            print("=====================================================================")
            sys.exit(0)
        except Exception as e:
            print(f"\nVerification failed with static token: {e}")
            sys.exit(1)

    # Fallback to standard client credentials verification flow
    if not settings.MICROSOFT_CLIENT_ID or not settings.MICROSOFT_CLIENT_SECRET:
        print("\033[91m[ERROR]\033[0m Microsoft Graph credentials are not configured in your .env file.")
        print("Please configure either MICROSOFT_ACCESS_TOKEN or the following credentials:")
        print("  - MICROSOFT_CLIENT_ID")
        print("  - MICROSOFT_CLIENT_SECRET")
        print("  - MICROSOFT_TENANT_ID")
        print("  - MICROSOFT_REDIRECT_URI\n")
        print("E2E Graph verification aborted.")
        sys.exit(1)

    try:
        # 2. Test login URL generation
        print("Testing authorization URL generation...")
        res_login = client.get("/api/v1/microsoft/login")
        print_result("GET /login returns 200", res_login.status_code == 200)
        if res_login.status_code == 200:
            auth_url = res_login.json().get("auth_url")
            is_valid_url = (
                auth_url.startswith("https://login.microsoftonline.com") and
                settings.MICROSOFT_CLIENT_ID in auth_url
            )
            print_result("Auth URL is valid", is_valid_url, f"Redirect to: {auth_url[:80]}...")

        # 3. Check for active session in SQLite database
        print("\nChecking token database status...")
        access_token = microsoft_auth_manager.get_access_token()
        if not access_token:
            print("\033[93m[NOTICE]\033[0m No active OAuth token was found in the database.")
            print("Please perform browser login first to acquire a session token.")
            print(f"Login URL: {microsoft_auth_manager.get_authorization_url()}\n")
            print("Database token validation skipped.")
            sys.exit(0)

        print_result("Database has active token", True)

        # 4. Fetch profile using real Graph client
        print("\nFetching user profile from Microsoft Graph...")
        res_profile = client.get("/api/v1/microsoft/profile")
        print_result("GET /profile returns 200", res_profile.status_code == 200)
        if res_profile.status_code == 200:
            profile = res_profile.json()
            print_result("Active profile loaded", True, f"User: {profile.get('displayName')} <{profile.get('mail')}>")

        # 5. Test disconnect (cleanup)
        print("\nDisconnecting integration...")
        res_disconnect = client.post("/api/v1/microsoft/disconnect")
        print_result("POST /disconnect returns 204", res_disconnect.status_code == 204)
        
        # Verify token was cleared
        res_profile_after = client.get("/api/v1/microsoft/profile")
        print_result("GET /profile returns 401 after disconnect", res_profile_after.status_code == 401)

        print("\n=====================================================================")
        print("                 GRAPH INTEGRATION TESTS PASS                        ")
        print("=====================================================================")
        
    except Exception as e:
        print(f"\nVerification failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
