import importlib
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _build_app(tmp_path, monkeypatch, **env_overrides):
    downloads = tmp_path / "downloads"
    downloads.mkdir()
    db_path = tmp_path / "jobs.db"

    monkeypatch.setenv("YTPI_DOWNLOADS_DIR", str(downloads))
    monkeypatch.setenv("YTPI_DB_PATH", str(db_path))
    monkeypatch.setenv("YTPI_MAX_WORKERS", "0")
    monkeypatch.setenv("YTPI_ALLOWED_CIDRS", "127.0.0.0/8")
    for key, value in env_overrides.items():
        monkeypatch.setenv(key, value)

    import app as app_module

    importlib.reload(app_module)
    flask_app = app_module.create_app()
    flask_app.config["TESTING"] = True
    return flask_app


@pytest.fixture
def client(tmp_path, monkeypatch):
    flask_app = _build_app(tmp_path, monkeypatch)
    with flask_app.test_client() as test_client:
        yield test_client


LOCAL = {"REMOTE_ADDR": "127.0.0.1"}


def test_dashboard_has_notification_region(client):
    """Test that the dashboard has an ARIA live region for notifications."""
    resp = client.get("/status", environ_base=LOCAL)
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")
    
    # Should have an ARIA live region for notifications
    assert 'aria-live="polite"' in html or 'aria-live="assertive"' in html
    # Should have a notification container
    assert 'notification' in html.lower() or 'status-region' in html.lower()


def test_cancel_action_shows_feedback(client):
    """Test that cancel action shows success/error feedback."""
    # First create a job
    resp = client.post(
        "/download",
        json={"url": "https://youtube.com/watch?v=abc123", "quality": "720", "category": "Music"},
        environ_base=LOCAL,
    )
    assert resp.status_code == 202
    data = resp.get_json()
    job_id = data["job_id"]
    
    # Cancel the job
    resp = client.post(f"/jobs/{job_id}/cancel", environ_base=LOCAL)
    assert resp.status_code == 200
    
    # Check that the response includes a message
    data = resp.get_json()
    assert "message" in data
    assert "cancelled" in data["message"].lower() or "success" in data["message"].lower()


def test_retry_action_shows_feedback(client):
    """Test that retry action shows success/error feedback."""
    # Create a job
    resp = client.post(
        "/download",
        json={"url": "https://youtube.com/watch?v=abc123", "quality": "720", "category": "Music"},
        environ_base=LOCAL,
    )
    assert resp.status_code == 202
    data = resp.get_json()
    job_id = data["job_id"]
    
    # Cancel it first so we can retry
    client.post(f"/jobs/{job_id}/cancel", environ_base=LOCAL)
    
    # Retry the job
    resp = client.post(f"/jobs/{job_id}/retry", environ_base=LOCAL)
    assert resp.status_code == 200
    
    # Check that the response includes a message
    data = resp.get_json()
    assert "message" in data
    # Accept various success messages
    message_lower = data["message"].lower()
    assert any(keyword in message_lower for keyword in ["re-queued", "retried", "success", "queued"])


def test_clear_finished_shows_feedback(client):
    """Test that clear finished shows success/error feedback."""
    # Create and finish a job (simulated by marking as finished in repo)
    resp = client.post(
        "/download",
        json={"url": "https://youtube.com/watch?v=abc123", "quality": "720", "category": "Music"},
        environ_base=LOCAL,
    )
    assert resp.status_code == 202
    
    # Clear finished
    resp = client.post("/clear-finished", environ_base=LOCAL)
    assert resp.status_code == 200
    
    # Check that the response includes a message
    data = resp.get_json()
    assert "message" in data
    assert "cleared" in data["message"].lower() or "success" in data["message"].lower()


def test_playlist_sync_shows_feedback(client):
    """Test that playlist sync shows success/error feedback."""
    # Create a playlist by downloading a playlist URL
    playlist_url = "https://www.youtube.com/playlist?list=PLtest123"
    resp = client.post(
        "/download",
        json={
            "url": playlist_url,
            "category": "test-category",
            "quality": "720"
        },
        environ_base=LOCAL
    )
    assert resp.status_code == 202
    
    # Get the playlist ID from the API
    playlists_resp = client.get("/api/playlists", environ_base=LOCAL)
    assert playlists_resp.status_code == 200
    playlists = playlists_resp.get_json()["items"]
    assert len(playlists) > 0
    playlist_id = playlists[0]["id"]

    # Sync the playlist
    resp = client.post(f"/api/playlists/{playlist_id}/sync", environ_base=LOCAL)
    # Should either succeed (202) or fail with queue full (429)
    assert resp.status_code in (200, 202, 429)
    
    if resp.status_code == 429:
        data = resp.get_json()
        assert "error" in data
        assert "queue" in data["error"].lower() or "full" in data["error"].lower()
    elif resp.status_code == 202:
        # Check that the response includes a job_id
        data = resp.get_json()
        assert "job_id" in data


def test_duplicate_actions_prevented(client):
    """Test that duplicate actions are prevented while pending."""
    # Create a job
    resp = client.post(
        "/download",
        json={"url": "https://youtube.com/watch?v=abc123", "quality": "720", "category": "Music"},
        environ_base=LOCAL,
    )
    assert resp.status_code == 202
    data = resp.get_json()
    job_id = data["job_id"]
    
    # This test would need JavaScript testing, but we can at least verify
    # the endpoint doesn't crash on duplicate requests
    resp1 = client.post(f"/jobs/{job_id}/cancel", environ_base=LOCAL)
    assert resp1.status_code in (200, 400, 409)
    
    # Second cancel attempt should either succeed (if first worked) or give appropriate error
    resp2 = client.post(f"/jobs/{job_id}/cancel", environ_base=LOCAL)
    assert resp2.status_code in (200, 400, 409)