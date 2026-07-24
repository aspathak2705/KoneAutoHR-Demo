import os
from pathlib import Path

# Paths
AUDIT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = AUDIT_DIR.parent
REPORTS_DIR = AUDIT_DIR / "reports"

# Ensure reports directory exists
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

# Test Variables
TEST_SESSION_ID = "test-session-audit"
TEST_EXCEL_PATH = "mock_inductees_audit.xlsx"
TEST_PPTX_PATH = "mock_deck_audit.pptx"

# DB Config
TEST_DATABASE_URL = "sqlite:///./autohr_audit.db"
