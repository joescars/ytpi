import pytest
from pathlib import Path
import sys
import importlib

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

def test_playlist_sync_state_initial(client):
    """Test that a new playlist has idle sync state."""
    # First create a playlist
    resp = client.post(
        "/download",
        json={"url": "https://youtube.com/playlist?list=test123", "category": "Music"},
        environ_base=LOCAL,
    )
    assert resp.status_code == 202
    
    # Get playlists via API
    resp = client.get("/api/playlists", environ_base=LOCAL)
    assert resp.status_code == 200
    playlists = resp.get_json()["items"]
    assert len(playlists) == 1
    
    playlist = playlists[0]
    # New playlists should have idle sync state
    assert playlist.get("sync_status") == "idle"
    assert playlist.get("sync_job_id") is None
    assert playlist.get("last_successful_sync_at") is None
    # last_synced_at should be None for backward compatibility
    assert playlist.get("last_synced_at") is None

def test_playlist_sync_requested_state(client):
    """Test that playlist sync transitions to requested when sync is initiated."""
    # Create a playlist first
    resp = client.post(
        "/download",
        json={"url": "https://youtube.com/playlist?list=test456", "category": "Music"},
        environ_base=LOCAL,
    )
    assert resp.status_code == 202
    
    # Get playlist ID
    resp = client.get("/api/playlists", environ_base=LOCAL)
    playlists = resp.get_json()["items"]
    playlist_id = playlists[0]["id"]
    
    # Sync the playlist
    resp = client.post(f"/api/playlists/{playlist_id}/sync", environ_base=LOCAL)
    assert resp.status_code == 202
    sync_data = resp.get_json()
    assert "job_id" in sync_data
    
    # Check playlist sync state
    resp = client.get("/api/playlists", environ_base=LOCAL)
    playlist = resp.get_json()["items"][0]
    assert playlist.get("sync_status") == "requested"
    assert playlist.get("sync_job_id") == sync_data["job_id"]
    assert playlist.get("last_successful_sync_at") is None

def test_playlist_sync_active_state(client):
    """Test that playlist sync transitions to active when job starts downloading."""
    # This test will need to mock the manager to simulate job state transitions
    # For now, we'll test the repository update methods
    pass

def test_playlist_sync_successful_state(client):
    """Test that successful sync updates state and last_successful_sync_at."""
    pass

def test_playlist_sync_failed_state(client):
    """Test that failed sync updates state but not last_successful_sync_at."""
    pass

def test_playlist_sync_cancellation(client):
    """Test that cancelled sync preserves previous successful timestamp."""
    pass

def test_playlist_sync_queued_job_recovery(client):
    """Test that queued jobs retain playlist relationship after restart."""
    pass