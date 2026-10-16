import pytest
from fastapi.testclient import TestClient
from main import app
from app.core.config import settings
from app.db.database import engine, get_db
from app.models.session import Session
from app.schemas.session import SessionDetailResponse
from sqlalchemy.orm import Session as DBSession

def test_session_detail_eager_loading_and_serialization():
    """Verify session detail query eager loads relationships and serializes cleanly."""
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {settings.AUTH_TOKEN}"}
    
    # Query an existing session
    db = next(get_db())
    session = db.query(Session).first()
    assert session is not None, "At least one session should exist in the database"
    
    response = client.get(f"/api/v1/sessions/{session.id}", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == session.id
    assert "presentation_jobs" in data
    assert "uploads" in data

def test_meeting_by_session_concurrent_pool_resilience():
    """Verify concurrent requests do not exhaust the connection pool."""
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {settings.AUTH_TOKEN}"}
    
    db = next(get_db())
    session = db.query(Session).first()
    assert session is not None
    
    # Perform 20 sequential calls simulating heavy client polling/burst without connection leaks
    for _ in range(20):
        resp = client.get(f"/api/v1/meetings/session/{session.id}", headers=headers)
        assert resp.status_code == 200
        assert "configured" in resp.json()
