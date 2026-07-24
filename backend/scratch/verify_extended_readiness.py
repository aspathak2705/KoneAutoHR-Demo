import sys
import os
import asyncio
from pathlib import Path
from fastapi.testclient import TestClient

# Resolve paths
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

os.environ.setdefault("DATABASE_URL", "sqlite:///./autohr.db")
os.environ.setdefault("UPLOAD_PATH", "./uploads")

from main import app
from app.db.database import SessionLocal
from app.models.runtime import Runtime
from app.services.runtime_scheduler_service import runtime_scheduler_service
from app.modules.meeting_bot.services.meeting_bot_service import meeting_bot_service
from app.modules.meeting_bot.media.audio_controller import get_audio_controller
from app.modules.presentation_observer.services.presentation_observer_service import presentation_observer_service

def test_authentication():
    print("\n[+] Running Authentication Test...")
    client = TestClient(app)
    
    # 1. Test missing token
    res = client.get("/api/v1/sessions")
    assert res.status_code == 401, f"Expected 401, got {res.status_code}"
    print("    - Missing token test: PASS")

    # 2. Test invalid token
    res = client.get("/api/v1/sessions", headers={"Authorization": "Bearer invalid_token"})
    assert res.status_code == 401, f"Expected 401, got {res.status_code}"
    print("    - Invalid token test: PASS")

    # 3. Test correct token
    res = client.get("/api/v1/sessions", headers={"Authorization": "Bearer autohr_master_secret_token_2026"})
    # Since sessions list might be empty or populated, we expect 200 OK
    assert res.status_code == 200, f"Expected 200, got {res.status_code}"
    print("    - Correct token test: PASS")

def test_concurrency_isolation():
    print("\n[+] Running Multi-session Concurrency & Isolation Test...")
    
    session1 = "test-session-concurrency-1"
    session2 = "test-session-concurrency-2"

    # 1. Verify independent bot contexts
    bot1 = meeting_bot_service.get_bot(session1)
    bot2 = meeting_bot_service.get_bot(session2)
    assert bot1 != bot2, "Bots must not be identical singleton instances."
    assert bot1.session_id == session1
    assert bot2.session_id == session2
    print("    - Isolated bot instances check: PASS")

    # 2. Verify independent audio controllers
    audio1 = get_audio_controller(session1)
    audio2 = get_audio_controller(session2)
    assert audio1 != audio2, "Audio controllers must not be identical singletons."
    assert audio1.session_id == session1
    assert audio2.session_id == session2
    print("    - Isolated audio instances check: PASS")

    # 3. Verify independent observers
    obs1 = presentation_observer_service.get_observer(session1)
    obs2 = presentation_observer_service.get_observer(session2)
    assert obs1 != obs2, "Observers must not be identical singletons."
    print("    - Isolated observer instances check: PASS")

def test_restart_recovery():
    print("\n[+] Running Restart Recovery Test...")
    db = SessionLocal()
    session_id = "test-session-recovery-restart"
    
    # Pre-seed runtime in stale CONNECTED state
    rt = db.query(Runtime).filter(Runtime.session_id == session_id).first()
    if not rt:
        rt = Runtime(session_id=session_id)
        db.add(rt)
    rt.state = "CONNECTED"
    rt.last_error = "Stale error info"
    db.commit()

    # Trigger recovery
    recovered = runtime_scheduler_service.startup_recovery(db)
    
    # Assert state reset to PREPARING
    db.refresh(rt)
    assert rt.state == "PREPARING", f"Expected PREPARING, got {rt.state}"
    assert rt.last_error is None, "Stale error must be cleared."
    print("    - Stale state reset to PREPARING check: PASS")
    
    # Clean up
    db.delete(rt)
    db.commit()
    db.close()

if __name__ == "__main__":
    print("==================================================")
    # Run tests
    test_authentication()
    test_concurrency_isolation()
    test_restart_recovery()
    print("==================================================")
    print("   ALL EXTENDED READINESS TESTS PASSED SUCCESSFULLY!  ")
    print("==================================================")
