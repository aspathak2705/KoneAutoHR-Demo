import pytest
from urllib.parse import urlparse


def validate_api_url_contract(raw_url: str, is_prod: bool, app_mode: str = "connected") -> str:
    """
    Python mirror of frontend validateApiBaseUrl logic in sessions-store.ts.
    Used for automated regression testing of CI/CD and deployment validation rules.
    """
    if app_mode == "ui_only" or raw_url == "ui_only":
        return "ui_only"

    if not raw_url:
        raise ValueError("CRITICAL: VITE_API_BASE_URL environment variable is missing.")

    parsed = urlparse(raw_url)
    if is_prod:
        clean_host = (parsed.hostname or "").lower().strip("[]")
        is_local = (
            clean_host == "localhost"
            or clean_host.endswith(".localhost")
            or clean_host == "127.0.0.1"
            or clean_host == "::1"
            or clean_host == "0.0.0.0"
            or clean_host.startswith("127.")
        )
        if is_local:
            raise ValueError(f"SECURITY VIOLATION: Production build must not point to local address ({clean_host}).")
        if parsed.scheme != "https":
            raise ValueError(f"SECURITY VIOLATION: Production build requires HTTPS protocol. Current URL: {raw_url}")

    return raw_url.rstrip("/")


def test_ui_only_mode_acceptance():
    """Verify ui_only mode returns 'ui_only' without requiring backend URL."""
    res = validate_api_url_contract("", is_prod=True, app_mode="ui_only")
    assert res == "ui_only"


def test_connected_mode_rejects_missing_url():
    """Verify connected mode rejects empty or missing URLs."""
    with pytest.raises(ValueError, match="CRITICAL: VITE_API_BASE_URL environment variable is missing"):
        validate_api_url_contract("", is_prod=True, app_mode="connected")


def test_connected_mode_rejects_loopback():
    """Verify connected mode rejects localhost and 127.0.0.1 variants."""
    for local_url in [
        "https://localhost:8000",
        "https://127.0.0.1:8000",
        "https://127.0.0.2:8443",
        "https://sub.localhost:8000",
        "https://[::1]:8000",
    ]:
        with pytest.raises(ValueError, match="SECURITY VIOLATION: Production build must not point to local address"):
            validate_api_url_contract(local_url, is_prod=True, app_mode="connected")


def test_connected_mode_rejects_insecure_http():
    """Verify connected mode rejects insecure HTTP for external endpoints."""
    with pytest.raises(ValueError, match="SECURITY VIOLATION: Production build requires HTTPS protocol"):
        validate_api_url_contract("http://api-demo.kone.com", is_prod=True, app_mode="connected")


def test_connected_mode_accepts_valid_https():
    """Verify connected mode accepts valid HTTPS external endpoints."""
    url = "https://api-demo.kone.com/v1/"
    res = validate_api_url_contract(url, is_prod=True, app_mode="connected")
    assert res == "https://api-demo.kone.com/v1"


def test_development_mode_allows_localhost():
    """Verify local development mode allows local addresses."""
    res = validate_api_url_contract("http://127.0.0.1:8000", is_prod=False, app_mode="connected")
    assert res == "http://127.0.0.1:8000"
