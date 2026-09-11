import pytest
import json
from pathlib import Path
import sys
import importlib
import time

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

def test_playlist_sync_lifecycle(client):
    """Test complete playlist sync lifecycle: requested -> active -> successful."""
    # Create a playlist
    resp = client.post(
        "/download",
        json={"url": "https://youtube.com/playlist?list=lifecycle123", "category": "Music"},
        environ_base=LOCAL,
    )
    assert resp.status_code == 202
    
    # Get playlist
    resp = client.get("/api/playlists", environ_base=LOCAL)
    playlists = resp.get_json()["items"]
    playlist_id = playlists[0]["id"]
    
    # Initial state should be idle
    assert playlists[0]["sync_status"] == "idle"
    assert playlists[0]["sync_job_id"] is None
    assert playlists[0]["last_successful_sync_at"] is None
    
    # Sync playlist - should go to "requested"
    resp = client.post(f"/api/playlists/{playlist_id}/sync", environ_base=LOCAL)
    assert resp.status_code == 202
    sync_data = resp.get_json()
    job_id = sync_data["job_id"]
    
    # Check playlist state is "requested" with job ID
    resp = client.get("/api/playlists", environ_base=LOCAL)
    playlist = resp.get_json()["items"][0]
    assert playlist["sync_status"] == "requested"
    assert playlist["sync_job_id"] == job_id
    assert playlist["last_successful_sync_at"] is None
    
    # Simulate job starting (in real app this would happen via worker)
    # Get repository and manually update job to downloading and playlist to active
    repo = client.application.config["ytpi_repo"]
    repo.update_job(job_id, status="downloading", started_at="2026-01-01T00:00:00+00:00")
    repo.update_playlist_sync_state(playlist_id, "active", sync_job_id=job_id)
    
    # Check playlist state is "active"
    resp = client.get("/api/playlists", environ_base=LOCAL)
    playlist = resp.get_json()["items"][0]
    assert playlist["sync_status"] == "active"
    
    # Simulate job finishing successfully
    repo.update_job(job_id, status="finished", finished_at="2026-01-01T00:01:00+00:00", progress=100.0)
    success_time = "2026-01-01T00:01:00+00:00"
    repo.update_playlist_sync_state(playlist_id, "successful", last_successful_sync_at=success_time)
    
    # Check playlist state is "successful" with timestamp
    resp = client.get("/api/playlists", environ_base=LOCAL)
    playlist = resp.get_json()["items"][0]
    assert playlist["sync_status"] == "successful"
    assert playlist["last_successful_sync_at"] == success_time
    assert playlist["sync_job_id"] == job_id  # Should still have job ID

def test_playlist_sync_failure_preserves_previous_success(client):
    """Test that failed sync preserves previous successful timestamp."""
    # Create a playlist
    resp = client.post(
        "/download",
        json={"url": "https://youtube.com/playlist?list=failtest123", "category": "Music"},
        environ_base=LOCAL,
    )
    assert resp.status_code == 202
    
    # Get playlist
    resp = client.get("/api/playlists", environ_base=LOCAL)
    playlist = resp.get_json()["items"][0]
    playlist_id = playlist["id"]
    
    # First, simulate a successful sync
    success_time = "2026-01-01T00:00:00+00:00"
    repo = client.application.config["ytpi_repo"]
    repo.update_playlist_sync_state(playlist_id, "successful", last_successful_sync_at=success_time)
    
    # Now simulate a failed sync
    resp = client.post(f"/api/playlists/{playlist_id}/sync", environ_base=LOCAL)
    assert resp.status_code == 202
    sync_data = resp.get_json()
    job_id = sync_data["job_id"]
    
    # Update to requested
    repo.update_playlist_sync_state(playlist_id, "requested", sync_job_id=job_id)
    
    # Simulate failure
    repo.update_job(job_id, status="error", finished_at="2026-01-01T00:02:00+00:00", error="Failed")
    repo.update_playlist_sync_state(playlist_id, "failed")
    
    # Check that last_successful_sync_at is still the original success time
    resp = client.get("/api/playlists", environ_base=LOCAL)
    playlist = resp.get_json()["items"][0]
    assert playlist["sync_status"] == "failed"
    assert playlist["last_successful_sync_at"] == success_time  # Preserved!
    assert playlist["sync_job_id"] == job_id  # Still has the failed job ID

def test_playlist_sync_cancellation_preserves_previous_success(client):
    """Test that cancelled sync preserves previous successful timestamp."""
    # Create a playlist
    resp = client.post(
        "/download",
        json={"url": "https://youtube.com/playlist?list=canceltest123", "category": "Music"},
        environ_base=LOCAL,
    )
    assert resp.status_code == 202
    
    # Get playlist
    resp = client.get("/api/playlists", environ_base=LOCAL)
    playlist = resp.get_json()["items"][0]
    playlist_id = playlist["id"]
    
    # First, simulate a successful sync
    success_time = "2026-01-01T00:00:00+00:00"
    repo = client.application.config["ytpi_repo"]
    repo.update_playlist_sync_state(playlist_id, "successful", last_successful_sync_at=success_time)
    
    # Now simulate a sync that gets cancelled
    resp = client.post(f"/api/playlists/{playlist_id}/sync", environ_base=LOCAL)
    assert resp.status_code == 202
    sync_data = resp.get_json()
    job_id = sync_data["job_id"]
    
    # Create the job (it's already created by the sync route)
    # Just update playlist state to requested
    repo.update_playlist_sync_state(playlist_id, "requested", sync_job_id=job_id)
    
    # Cancel the job
    resp = client.post(f"/jobs/{job_id}/cancel", environ_base=LOCAL)
    assert resp.status_code == 200
    
    # Check that last_successful_sync_at is still the original success time
    resp = client.get("/api/playlists", environ_base=LOCAL)
    playlist = resp.get_json()["items"][0]
    assert playlist["sync_status"] == "failed"  # Cancellation sets to failed
    assert playlist["last_successful_sync_at"] == success_time  # Preserved!

def test_playlist_sync_retry_resets_state(client):
    """Test that retrying a failed sync resets state to requested."""
    # Create a playlist
    resp = client.post(
        "/download",
        json={"url": "https://youtube.com/playlist?list=retrytest123", "category": "Music"},
        environ_base=LOCAL,
    )
    assert resp.status_code == 202
    
    # Get playlist
    resp = client.get("/api/playlists", environ_base=LOCAL)
    playlist = resp.get_json()["items"][0]
    playlist_id = playlist["id"]
    
    # Simulate a failed sync
    repo = client.application.config["ytpi_repo"]
    job_id = "test-job-123"
    repo.create_job(job_id, playlist["url"], playlist["category"], playlist["quality"])
    repo.update_job(job_id, status="error", finished_at="2026-01-01T00:00:00+00:00", error="Failed")
    repo.update_playlist_sync_state(playlist_id, "failed", sync_job_id=job_id)
    
    # Retry the job
    resp = client.post(f"/jobs/{job_id}/retry", environ_base=LOCAL)
    assert resp.status_code == 200
    
    # Check playlist state is reset to "requested"
    resp = client.get("/api/playlists", environ_base=LOCAL)
    playlist = resp.get_json()["items"][0]
    assert playlist["sync_status"] == "requested"
    assert playlist["sync_job_id"] == job_id  # Still has same job ID

def test_playlist_sync_queued_job_recovery(client, tmp_path, monkeypatch):
    """Test that queued jobs retain playlist relationship after restart."""
    # First create a database with a queued playlist job
    downloads = tmp_path / "downloads"
    downloads.mkdir(exist_ok=True)
    db_path = tmp_path / "jobs.db"
    
    # Create initial app
    monkeypatch.setenv("YTPI_DOWNLOADS_DIR", str(downloads))
    monkeypatch.setenv("YTPI_DB_PATH", str(db_path))
    monkeypatch.setenv("YTPI_MAX_WORKERS", "0")
    monkeypatch.setenv("YTPI_ALLOWED_CIDRS", "127.0.0.0/8")
    
    import app as app_module
    importlib.reload(app_module)
    flask_app = app_module.create_app()
    flask_app.config["TESTING"] = True
    
    with flask_app.test_client() as test_client:
        # Create a playlist
        resp = test_client.post(
            "/download",
            json={"url": "https://youtube.com/playlist?list=recovery123", "category": "Music"},
            environ_base=LOCAL,
        )
        assert resp.status_code == 202
        
        # Get playlist
        resp = test_client.get("/api/playlists", environ_base=LOCAL)
        playlist = resp.get_json()["items"][0]
        playlist_id = playlist["id"]
        
        # Sync playlist to create job
        resp = test_client.post(f"/api/playlists/{playlist_id}/sync", environ_base=LOCAL)
        assert resp.status_code == 202
        sync_data = resp.get_json()
        job_id = sync_data["job_id"]
        
        # Verify playlist has requested state with job ID
        resp = test_client.get("/api/playlists", environ_base=LOCAL)
        playlist = resp.get_json()["items"][0]
        assert playlist["sync_status"] == "requested"
        assert playlist["sync_job_id"] == job_id
    
    # Now simulate app restart - create new app with same database
    importlib.reload(app_module)
    flask_app2 = app_module.create_app()
    flask_app2.config["TESTING"] = True
    
    with flask_app2.test_client() as test_client2:
        # Check playlist still has requested state with job ID
        resp = test_client2.get("/api/playlists", environ_base=LOCAL)
        playlist = resp.get_json()["items"][0]
        assert playlist["sync_status"] == "requested"
        assert playlist["sync_job_id"] == job_id
        
        # Check job is still queued
        repo = test_client2.application.config["ytpi_repo"]
        job = repo.get_job(job_id)
        assert job["status"] == "queued"

def test_playlist_sync_state_api_exposed(client):
    """Test that sync state is exposed through API."""
    # Create a playlist
    resp = client.post(
        "/download",
        json={"url": "https://youtube.com/playlist?list=apitest123", "category": "Music"},
        environ_base=LOCAL,
    )
    assert resp.status_code == 202
    
    # Get playlists via API
    resp = client.get("/api/playlists", environ_base=LOCAL)
    assert resp.status_code == 200
    playlists = resp.get_json()["items"]
    assert len(playlists) == 1
    
    # Check API includes all sync state fields
    playlist = playlists[0]
    required_fields = ["sync_status", "sync_job_id", "last_successful_sync_at", "last_synced_at"]
    for field in required_fields:
        assert field in playlist, f"Missing field: {field}"
    
    # Initial values
    assert playlist["sync_status"] == "idle"
    assert playlist["sync_job_id"] is None
    assert playlist["last_successful_sync_at"] is None
    
    # Sync and check updated fields
    playlist_id = playlist["id"]
    resp = client.post(f"/api/playlists/{playlist_id}/sync", environ_base=LOCAL)
    assert resp.status_code == 202
    job_id = resp.get_json()["job_id"]
    
    # Check updated state
    resp = client.get("/api/playlists", environ_base=LOCAL)
    playlist = resp.get_json()["items"][0]
    assert playlist["sync_status"] == "requested"
    assert playlist["sync_job_id"] == job_id
    assert playlist["last_successful_sync_at"] is None  # Not successful yet

def test_backward_compatibility_last_synced_at(client):
    """Test backward compatibility for last_synced_at field."""
    # Create a playlist
    resp = client.post(
        "/download",
        json={"url": "https://youtube.com/playlist?list=backcompat123", "category": "Music"},
        environ_base=LOCAL,
    )
    assert resp.status_code == 202
    
    # Get playlist
    resp = client.get("/api/playlists", environ_base=LOCAL)
    playlist = resp.get_json()["items"][0]
    playlist_id = playlist["id"]
    
    # Simulate successful sync
    repo = client.application.config["ytpi_repo"]
    success_time = "2026-01-01T00:00:00+00:00"
    repo.update_playlist_sync_state(playlist_id, "successful", last_successful_sync_at=success_time)
    
    # Check that last_synced_at is also set (for backward compatibility)
    resp = client.get("/api/playlists", environ_base=LOCAL)
    playlist = resp.get_json()["items"][0]
    assert playlist["last_synced_at"] == success_time
    assert playlist["last_successful_sync_at"] == success_time
    assert playlist["last_synced_at"] == playlist["last_successful_sync_at"]
    
    # Now simulate a failed sync - last_synced_at should NOT be updated
    resp = client.post(f"/api/playlists/{playlist_id}/sync", environ_base=LOCAL)
    job_id = resp.get_json()["job_id"]
    repo.update_job(job_id, status="error", finished_at="2026-01-01T00:01:00+00:00")
    repo.update_playlist_sync_state(playlist_id, "failed")
    
    # Check that last_synced_at still has original success time
    resp = client.get("/api/playlists", environ_base=LOCAL)
    playlist = resp.get_json()["items"][0]
    assert playlist["last_synced_at"] == success_time  # Unchanged
    assert playlist["last_successful_sync_at"] == success_time  # Unchanged