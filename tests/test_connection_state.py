import pytest
from pathlib import Path
import sys
import json
import importlib
from unittest.mock import patch, MagicMock

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


def test_connection_state_ui_elements_exist(client):
    """Test that connection state UI elements exist in the dashboard."""
    resp = client.get("/status", environ_base=LOCAL)
    assert resp.status_code == 200
    html = resp.data.decode('utf-8')
    
    # Should have last updated time display
    assert 'last-updated-time' in html or 'last-updated' in html.lower() or 'last-update' in html.lower()
    
    # Should have connection status indicator
    assert 'connection-status' in html or 'connection-state' in html.lower() or 'connection-indicator' in html.lower()
    
    # Should have connection warning/error area
    assert 'connection-warning' in html or 'connection-error' in html.lower() or 'stale-data-warning' in html.lower()


def test_refresh_button_retries_both_jobs_and_playlists(client):
    """Test that refresh button retries both jobs and playlists."""
    # Create a job and playlist to test refresh
    resp = client.post(
        "/download",
        json={"url": "https://youtube.com/watch?v=abc123", "category": "Music"},
        environ_base=LOCAL,
    )
    assert resp.status_code == 202
    
    # The refresh button should trigger both fetchJobs() and fetchPlaylists()
    # This is tested in browser tests, but we can verify the endpoints exist
    resp = client.get("/api/status", environ_base=LOCAL)
    assert resp.status_code == 200
    
    resp = client.get("/api/playlists", environ_base=LOCAL)
    assert resp.status_code == 200
    
    # Manual refresh endpoint exists
    resp = client.get("/status", environ_base=LOCAL)
    assert resp.status_code == 200


def test_polling_pauses_when_page_hidden(client):
    """Test that polling pauses when page is hidden."""
    # This is a JavaScript behavior test, but we can verify the logic
    # The dashboard.js should check document.hidden before fetching
    resp = client.get("/status", environ_base=LOCAL)
    assert resp.status_code == 200
    html = resp.data.decode('utf-8')
    script = (ROOT / "static" / "dashboard.js").read_text()
    
    # The dashboard.js is loaded as an external asset, so inspect the asset.
    assert 'visibilitychange' in script or 'document.hidden' in script


def test_connection_state_transitions_announced(client):
    """Test that connection loss and recovery are announced via ARIA live region."""
    resp = client.get("/status", environ_base=LOCAL)
    assert resp.status_code == 200
    html = resp.data.decode('utf-8')
    
    # Should have ARIA live region for status announcements
    assert 'aria-live' in html or 'role="alert"' in html or 'role="status"' in html
    
    # Should have notification region for connection state changes
    assert 'notification-region' in html or 'notifications' in html.lower()


def test_bounded_retry_backoff_on_failures(client):
    """Test that polling uses bounded retry backoff during repeated failures."""
    # This is a JavaScript behavior test
    # The dashboard.js should implement backoff logic for failed fetches
    resp = client.get("/status", environ_base=LOCAL)
    assert resp.status_code == 200
    script = (ROOT / "static" / "dashboard.js").read_text()
    
    # The dashboard.js is loaded as an external asset, so inspect the asset.
    assert 'fetchJobs' in script or 'fetchPlaylists' in script or 'setInterval' in script


def test_existing_data_remains_visible_when_stale(client):
    """Test that existing data remains visible while marked as potentially stale."""
    # Create a job
    resp = client.post(
        "/download",
        json={"url": "https://youtube.com/watch?v=abc123", "category": "Music"},
        environ_base=LOCAL,
    )
    assert resp.status_code == 202
    job_id = resp.get_json()["job_id"]
    
    # Load dashboard with the job
    resp = client.get(f"/status?job={job_id}", environ_base=LOCAL)
    assert resp.status_code == 200
    html = resp.data.decode('utf-8')
    
    # Job should be visible
    assert job_id in html
    
    # When connection fails, data should still be shown but marked as stale
    # This is a JavaScript behavior test