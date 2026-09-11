import pytest
from pathlib import Path
import sys
import json
import importlib
import tempfile

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


def test_job_has_progress_stage_field_in_api(client):
    """Test that job API includes progress_stage field."""
    # Enqueue a job
    resp = client.post(
        "/download",
        json={"url": "https://youtube.com/watch?v=abc123", "category": "Music"},
        environ_base=LOCAL,
    )
    assert resp.status_code == 202
    job_id = resp.get_json()["job_id"]

    # Check job status via /api/status
    resp = client.get("/api/status", environ_base=LOCAL)
    assert resp.status_code == 200
    data = resp.get_json()
    
    # Find our job
    job = None
    for j in data["items"]:
        if j["id"] == job_id:
            job = j
            break
    
    assert job is not None
    # Progress stage should exist and be a string
    assert "progress_stage" in job
    assert isinstance(job["progress_stage"], str)
    # Initial stage should be "Preparing" for queued jobs
    assert job["progress_stage"] == "Preparing"


def test_job_output_endpoint_includes_progress_stage(client):
    """Test that /job_output/<job_id> includes progress_stage."""
    # Enqueue a job
    resp = client.post(
        "/download",
        json={"url": "https://youtube.com/watch?v=abc123", "category": "Music"},
        environ_base=LOCAL,
    )
    assert resp.status_code == 202
    job_id = resp.get_json()["job_id"]

    # Check job_output endpoint
    resp = client.get(f"/job_output/{job_id}", environ_base=LOCAL)
    assert resp.status_code == 200
    job = resp.get_json()
    
    # Progress stage should exist
    assert "progress_stage" in job
    assert isinstance(job["progress_stage"], str)
    assert job["progress_stage"] == "Preparing"


def test_can_update_job_with_progress_stage(client):
    """Test that we can update a job with progress_stage field."""
    # Create a job
    resp = client.post(
        "/download",
        json={"url": "https://youtube.com/watch?v=abc123", "category": "Music"},
        environ_base=LOCAL,
    )
    assert resp.status_code == 202
    job_id = resp.get_json()["job_id"]
    
    # Get repository from app config
    repository = client.application.config["ytpi_repo"]
    
    # Update job with progress stage
    repository.update_job(
        job_id,
        status="downloading",
        progress=25.0,
        progress_stage="Downloading item 1 of 3"
    )
    
    # Check updated job via API
    resp = client.get(f"/job_output/{job_id}", environ_base=LOCAL)
    assert resp.status_code == 200
    job = resp.get_json()
    
    assert job["progress_stage"] == "Downloading item 1 of 3"
    assert job["progress"] == 25.0
    assert job["status"] == "downloading"


def test_playlist_fields_in_job_api(client):
    """Test that playlist-specific progress fields exist in job API."""
    # Create a playlist job
    resp = client.post(
        "/download",
        json={
            "url": "https://youtube.com/playlist?list=test123",
            "category": "Music",
            "quality": "720"
        },
        environ_base=LOCAL,
    )
    assert resp.status_code == 202
    job_id = resp.get_json()["job_id"]
    
    # Get repository from app config
    repository = client.application.config["ytpi_repo"]
    
    # Update with playlist-specific progress fields
    repository.update_job(
        job_id,
        status="downloading",
        progress=33.3,  # Current file transfer percentage
        playlist_item_position=2,
        playlist_item_total=6,
        progress_stage="Downloading item 2 of 6"
    )
    
    # Check updated job
    resp = client.get(f"/job_output/{job_id}", environ_base=LOCAL)
    assert resp.status_code == 200
    job = resp.get_json()
    
    assert job["progress_stage"] == "Downloading item 2 of 6"
    assert "playlist_item_position" in job
    assert "playlist_item_total" in job
    assert job["playlist_item_position"] == 2
    assert job["playlist_item_total"] == 6
    # Overall progress should NOT be 100% when individual file completes
    assert job["progress"] == 33.3


def test_progress_resets_on_retry(client):
    """Test that progress fields reset when a job is retried."""
    # Create and fail a job
    resp = client.post(
        "/download",
        json={"url": "https://youtube.com/watch?v=abc123", "category": "Music"},
        environ_base=LOCAL,
    )
    assert resp.status_code == 202
    job_id = resp.get_json()["job_id"]
    
    repository = client.application.config["ytpi_repo"]
    
    # Mark job as failed with progress
    repository.update_job(
        job_id,
        status="error",
        progress=50.0,
        progress_stage="Downloading",
        error="Network error"
    )
    
    # Retry the job
    resp = client.post(f"/jobs/{job_id}/retry", environ_base=LOCAL)
    assert resp.status_code == 200
    
    # Check retried job - progress and stage should be reset
    resp = client.get(f"/job_output/{job_id}", environ_base=LOCAL)
    assert resp.status_code == 200
    job = resp.get_json()
    
    # Progress should be reset to 0
    assert job["progress"] == 0.0
    # Stage should be reset to initial state
    assert job["progress_stage"] == "Preparing"
    # Status should be queued
    assert job["status"] == "queued"