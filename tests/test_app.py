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


def test_healthz(client):
    resp = client.get("/healthz", environ_base=LOCAL)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "ok"


def test_readyz(client):
    resp = client.get("/readyz", environ_base=LOCAL)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "ready"
    assert data["downloads_writable"] is True
    assert data["queue_available"] is True


def test_blocks_non_local_ip(client):
    resp = client.get("/", environ_base={"REMOTE_ADDR": "8.8.8.8"})
    assert resp.status_code == 403


def test_homepage_loads(client):
    resp = client.get("/", environ_base=LOCAL)
    assert resp.status_code == 200
    assert b"ytpi | Queue Download" in resp.data


def test_status_page_loads(client):
    resp = client.get("/status", environ_base=LOCAL)
    assert resp.status_code == 200


def test_rejects_path_traversal_category(client):
    resp = client.post(
        "/download",
        json={"url": "https://youtube.com/watch?v=abc123", "category": "../../etc"},
        environ_base=LOCAL,
    )
    assert resp.status_code == 400


def test_enqueue_download(client):
    resp = client.post(
        "/download",
        json={"url": "https://youtube.com/watch?v=abc123", "quality": "720", "category": "Music"},
        environ_base=LOCAL,
    )
    assert resp.status_code == 202
    data = resp.get_json()
    assert "job_id" in data

    status_resp = client.get("/api/status", environ_base=LOCAL)
    assert status_resp.status_code == 200
    status_data = status_resp.get_json()
    assert status_data["total"] >= 1


def test_enqueue_download_form_encoded(client):
    resp = client.post(
        "/download",
        data={"url": "https://youtube.com/watch?v=abc123", "quality": "720", "category": "Music"},
        environ_base=LOCAL,
    )
    # Non-JSON submissions redirect to /status on success.
    assert resp.status_code == 302
    assert "/status" in resp.headers["Location"]


def test_enqueue_download_custom_category(client):
    resp = client.post(
        "/download",
        json={
            "url": "https://youtube.com/watch?v=abc123",
            "category": "__custom__",
            "customCategory": "My Show",
        },
        environ_base=LOCAL,
    )
    assert resp.status_code == 202
    data = resp.get_json()

    status_resp = client.get("/api/status", environ_base=LOCAL)
    items = status_resp.get_json()["items"]
    job = next(j for j in items if j["id"] == data["job_id"])
    assert job["category"] == "My Show"


def test_enqueue_download_custom_category_missing_name(client):
    resp = client.post(
        "/download",
        json={"url": "https://youtube.com/watch?v=abc123", "category": "__custom__"},
        environ_base=LOCAL,
    )
    assert resp.status_code == 400


def test_enqueue_download_multi_url_string(client):
    resp = client.post(
        "/download",
        json={"url": "https://youtube.com/watch?v=a,https://youtube.com/watch?v=b"},
        environ_base=LOCAL,
    )
    assert resp.status_code == 202
    data = resp.get_json()
    assert "job_ids" in data
    assert len(data["job_ids"]) == 2


def test_enqueue_download_multi_url_array(client):
    resp = client.post(
        "/download",
        json={"urls": ["https://youtube.com/watch?v=a", "https://youtube.com/watch?v=b"]},
        environ_base=LOCAL,
    )
    assert resp.status_code == 202
    data = resp.get_json()
    assert len(data["job_ids"]) == 2


def test_playlist_url_is_stored_and_listed(client):
    url = "https://www.youtube.com/playlist?list=PLabc123"
    resp = client.post("/download", json={"url": url}, environ_base=LOCAL)
    assert resp.status_code == 202

    playlists = client.get("/api/playlists", environ_base=LOCAL)
    assert playlists.status_code == 200
    item = playlists.get_json()["items"][0]
    assert item["url"] == url
    assert item["name"] == "PLabc123"


def test_sync_playlist_enqueues_saved_url(client):
    url = "https://www.youtube.com/playlist?list=PLsync123"
    client.post("/download", json={"url": url}, environ_base=LOCAL)
    playlist = client.get("/api/playlists", environ_base=LOCAL).get_json()["items"][0]

    resp = client.post(f"/api/playlists/{playlist['id']}/sync", environ_base=LOCAL)
    assert resp.status_code == 202
    job = client.get("/api/status", environ_base=LOCAL).get_json()["items"][0]
    assert job["url"] == url


def test_playlist_name_can_be_updated_after_download(client):
    url = "https://www.youtube.com/playlist?list=PLnamed123"
    client.post("/download", json={"url": url}, environ_base=LOCAL)
    repo = client.application.config["ytpi_repo"]
    repo.update_playlist_name(url, "My Favorite Videos")

    playlist = client.get("/api/playlists", environ_base=LOCAL).get_json()["items"][0]
    assert playlist["name"] == "My Favorite Videos"


def test_yt_dlp_finished_playlist_output_is_recognized():
    from ytpi_app.manager import PLAYLIST_TITLE_RE

    match = PLAYLIST_TITLE_RE.search("[download] Finished downloading playlist: My Favorite Videos")
    assert match
    assert match.group(1) == "My Favorite Videos"


def test_enqueue_download_invalid_url(client):
    resp = client.post(
        "/download",
        json={"url": "not-a-url"},
        environ_base=LOCAL,
    )
    assert resp.status_code == 400


def test_enqueue_download_missing_url(client):
    resp = client.post(
        "/download",
        json={},
        environ_base=LOCAL,
    )
    assert resp.status_code == 400


def test_enqueue_download_queue_full(tmp_path, monkeypatch):
    flask_app = _build_app(tmp_path, monkeypatch, YTPI_MAX_QUEUE_SIZE="1")
    with flask_app.test_client() as test_client:
        first = test_client.post(
            "/download", json={"url": "https://youtube.com/watch?v=abc123"}, environ_base=LOCAL
        )
        assert first.status_code == 202

        second = test_client.post(
            "/download", json={"url": "https://youtube.com/watch?v=def456"}, environ_base=LOCAL
        )
        assert second.status_code == 429


def test_enqueue_download_blocks_private_url_when_enabled(tmp_path, monkeypatch):
    flask_app = _build_app(tmp_path, monkeypatch, YTPI_BLOCK_PRIVATE_URLS="1")
    with flask_app.test_client() as test_client:
        resp = test_client.post(
            "/download", json={"url": "http://192.168.1.5/video"}, environ_base=LOCAL
        )
        assert resp.status_code == 400


def test_enqueue_download_allows_private_url_by_default(client):
    resp = client.post(
        "/download", json={"url": "http://192.168.1.5/video"}, environ_base=LOCAL
    )
    assert resp.status_code == 202


def test_enqueue_download_body_too_large(tmp_path, monkeypatch):
    flask_app = _build_app(tmp_path, monkeypatch, YTPI_MAX_CONTENT_LENGTH="1024")
    with flask_app.test_client() as test_client:
        big_url = "https://youtube.com/watch?v=" + ("a" * 5000)
        resp = test_client.post("/download", json={"url": big_url}, environ_base=LOCAL)
        assert resp.status_code == 413


def test_enqueue_audio_only_mp3(client):
    resp = client.post(
        "/download",
        json={
            "url": "https://youtube.com/watch?v=abc123",
            "audio_only": "true",
            "audio_format": "mp3",
            "category": "Music",
        },
        environ_base=LOCAL,
    )
    assert resp.status_code == 202
    data = resp.get_json()
    assert "job_id" in data

    # Verify the job was stored with audio_only=1 and audio_format="mp3"
    status_resp = client.get("/api/status", environ_base=LOCAL)
    items = status_resp.get_json()["items"]
    job = next(j for j in items if j["id"] == data["job_id"])
    assert job["audio_only"] == 1
    assert job["audio_format"] == "mp3"
    assert job["category"] == "audio-only"


def test_enqueue_audio_only_wav(client):
    resp = client.post(
        "/download",
        json={
            "url": "https://youtube.com/watch?v=abc123",
            "audio_only": "true",
            "audio_format": "wav",
        },
        environ_base=LOCAL,
    )
    assert resp.status_code == 202
    data = resp.get_json()
    assert "job_id" in data

    status_resp = client.get("/api/status", environ_base=LOCAL)
    items = status_resp.get_json()["items"]
    job = next(j for j in items if j["id"] == data["job_id"])
    assert job["audio_only"] == 1
    assert job["audio_format"] == "wav"
    assert job["category"] == "audio-only"


def test_enqueue_audio_only_invalid_format_defaults_to_mp3(client):
    resp = client.post(
        "/download",
        json={
            "url": "https://youtube.com/watch?v=abc123",
            "audio_only": "true",
            "audio_format": "flac",
        },
        environ_base=LOCAL,
    )
    assert resp.status_code == 202
    data = resp.get_json()
    assert "job_id" in data

    status_resp = client.get("/api/status", environ_base=LOCAL)
    items = status_resp.get_json()["items"]
    job = next(j for j in items if j["id"] == data["job_id"])
    assert job["audio_only"] == 1
    assert job["audio_format"] == "mp3"


def test_enqueue_without_audio_only_is_false(client):
    resp = client.post(
        "/download",
        json={"url": "https://youtube.com/watch?v=abc123", "quality": "1080"},
        environ_base=LOCAL,
    )
    assert resp.status_code == 202
    data = resp.get_json()

    status_resp = client.get("/api/status", environ_base=LOCAL)
    items = status_resp.get_json()["items"]
    job = next(j for j in items if j["id"] == data["job_id"])
    assert job["audio_only"] == 0


def test_api_status_filter_by_status(client):
    client.post("/download", json={"url": "https://youtube.com/watch?v=abc123"}, environ_base=LOCAL)

    resp = client.get("/api/status?status=queued", environ_base=LOCAL)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["total"] >= 1
    assert all(job["status"] == "queued" for job in data["items"])

    resp = client.get("/api/status?status=finished", environ_base=LOCAL)
    assert resp.get_json()["total"] == 0


def test_job_output_not_found(client):
    resp = client.get("/job_output/does-not-exist", environ_base=LOCAL)
    assert resp.status_code == 404


def test_job_output_found(client):
    enqueue_resp = client.post(
        "/download", json={"url": "https://youtube.com/watch?v=abc123"}, environ_base=LOCAL
    )
    job_id = enqueue_resp.get_json()["job_id"]

    resp = client.get(f"/job_output/{job_id}", environ_base=LOCAL)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "queued"


def test_cancel_queued_job(client):
    enqueue_resp = client.post(
        "/download", json={"url": "https://youtube.com/watch?v=abc123"}, environ_base=LOCAL
    )
    job_id = enqueue_resp.get_json()["job_id"]

    resp = client.post(f"/jobs/{job_id}/cancel", environ_base=LOCAL)
    assert resp.status_code == 200

    status_resp = client.get(f"/job_output/{job_id}", environ_base=LOCAL)
    assert status_resp.get_json()["status"] == "cancelled"


def test_cancel_nonexistent_job(client):
    resp = client.post("/jobs/does-not-exist/cancel", environ_base=LOCAL)
    assert resp.status_code == 404


def test_retry_cancelled_job(client):
    enqueue_resp = client.post(
        "/download", json={"url": "https://youtube.com/watch?v=abc123"}, environ_base=LOCAL
    )
    job_id = enqueue_resp.get_json()["job_id"]
    client.post(f"/jobs/{job_id}/cancel", environ_base=LOCAL)

    resp = client.post(f"/jobs/{job_id}/retry", environ_base=LOCAL)
    assert resp.status_code == 200

    status_resp = client.get(f"/job_output/{job_id}", environ_base=LOCAL)
    assert status_resp.get_json()["status"] == "queued"


def test_retry_queued_job_rejected(client):
    enqueue_resp = client.post(
        "/download", json={"url": "https://youtube.com/watch?v=abc123"}, environ_base=LOCAL
    )
    job_id = enqueue_resp.get_json()["job_id"]

    resp = client.post(f"/jobs/{job_id}/retry", environ_base=LOCAL)
    assert resp.status_code == 400


def test_clear_finished(client):
    resp = client.post("/clear-finished", environ_base=LOCAL)
    assert resp.status_code == 200
    data = resp.get_json()
    assert "Cleared" in data["message"]


def test_share_get_disabled_by_config(tmp_path, monkeypatch):
    flask_app = _build_app(tmp_path, monkeypatch, YTPI_ENABLE_SHARE_GET="0")
    with flask_app.test_client() as test_client:
        resp = test_client.get(
            "/share", query_string={"url": "https://youtube.com/watch?v=abc123"}, environ_base=LOCAL
        )
        assert resp.status_code == 405


def test_share_get_requires_token_when_unset(client):
    # Default config has no YTPI_SHARE_TOKEN set - endpoint must refuse rather than
    # operate unauthenticated.
    resp = client.get(
        "/share", query_string={"url": "https://youtube.com/watch?v=abc123"}, environ_base=LOCAL
    )
    assert resp.status_code == 403


def test_share_get_rejects_invalid_token(tmp_path, monkeypatch):
    flask_app = _build_app(tmp_path, monkeypatch, YTPI_SHARE_TOKEN="secret")
    with flask_app.test_client() as test_client:
        resp = test_client.get(
            "/share",
            query_string={"url": "https://youtube.com/watch?v=abc123", "token": "wrong"},
            environ_base=LOCAL,
        )
        assert resp.status_code == 401


def test_share_get_accepts_valid_token(tmp_path, monkeypatch):
    flask_app = _build_app(tmp_path, monkeypatch, YTPI_SHARE_TOKEN="secret")
    with flask_app.test_client() as test_client:
        resp = test_client.get(
            "/share",
            query_string={
                "url": "https://youtube.com/watch?v=abc123",
                "token": "secret",
                "redirect": "0",
            },
            environ_base=LOCAL,
        )
        assert resp.status_code == 202


def test_trust_proxy_uses_forwarded_header(tmp_path, monkeypatch):
    flask_app = _build_app(tmp_path, monkeypatch, YTPI_TRUST_PROXY="1")
    with flask_app.test_client() as test_client:
        # REMOTE_ADDR is a disallowed public IP, but X-Forwarded-For claims localhost.
        resp = test_client.get(
            "/healthz",
            environ_base={"REMOTE_ADDR": "8.8.8.8"},
            headers={"X-Forwarded-For": "127.0.0.1"},
        )
        assert resp.status_code == 200


def test_trust_proxy_disabled_ignores_forwarded_header(client):
    # YTPI_TRUST_PROXY is off by default; a spoofed header must not bypass the allowlist.
    resp = client.get(
        "/healthz",
        environ_base={"REMOTE_ADDR": "8.8.8.8"},
        headers={"X-Forwarded-For": "127.0.0.1"},
    )
    assert resp.status_code == 403


def test_form_preserves_values_on_validation_error(client):
    """Test that form preserves submitted values when validation fails."""
    # Submit form with invalid URL
    resp = client.post(
        "/download",
        data={
            "url": "not-a-valid-url",
            "category": "Music",
            "quality": "720",
            "audio_only": "on",
            "audio_format": "mp3"
        },
        environ_base=LOCAL,
    )
    assert resp.status_code == 400
    
    # Check that response contains submitted values
    html = resp.data.decode("utf-8")
    # URL field should show "not-a-valid-url" in textarea
    assert 'not-a-valid-url' in html
    # Category dropdown should show "Music" selected
    assert 'value="Music" selected' in html or 'selected>Music<' in html
    # Quality dropdown should show "720" selected
    assert 'value="720" selected' in html or 'selected>720<' in html
    # Audio-only checkbox should be checked
    assert 'checked' in html
    # Audio format should show "mp3" selected
    assert 'value="mp3" selected' in html or 'selected>MP3<' in html

def test_form_shows_inline_error_for_invalid_url(client):
    """Test that invalid URLs show inline error with field focus."""
    resp = client.post(
        "/download",
        data={"url": "not-a-valid-url"},
        environ_base=LOCAL,
    )
    assert resp.status_code == 400
    
    html = resp.data.decode("utf-8")
    # Should show specific error about invalid URL
    assert "invalid" in html.lower() or "error" in html.lower()
    # Error should be associated with URL field
    # (e.g., aria-describedby, data-error attribute, or nearby error message)

def test_form_preserves_custom_category(client):
    """Test that custom category is preserved on validation error."""
    resp = client.post(
        "/download",
        data={
            "url": "not-a-valid-url",
            "category": "__custom__",
            "customCategory": "My Custom Videos"
        },
        environ_base=LOCAL,
    )
    assert resp.status_code == 400
    
    html = resp.data.decode("utf-8")
    # Custom category field should show "My Custom Videos"
    assert 'value="My Custom Videos"' in html
    # __custom__ should be selected in category dropdown
    assert 'value="__custom__" selected' in html or 'selected>Custom...<' in html

def test_form_error_focuses_url_field(client):
    """Test that form errors cause focus to move to URL field."""
    resp = client.post(
        "/download",
        data={"url": "not-a-valid-url"},
        environ_base=LOCAL,
    )
    assert resp.status_code == 400
    
    html = resp.data.decode("utf-8")
    # Should have form-error element
    assert 'id="form-error"' in html
    # URL field should have aria-describedby pointing to form-error
    assert 'aria-describedby="form-error"' in html

def test_form_shows_specific_invalid_url_error(client):
    """Test that form shows specific invalid URL in error message."""
    resp = client.post(
        "/download",
        data={"url": "not-a-valid-url"},
        environ_base=LOCAL,
    )
    assert resp.status_code == 400
    
    html = resp.data.decode("utf-8")
    # Should show specific invalid URL
    assert "Invalid URL: not-a-valid-url" in html

def test_form_shows_multiple_invalid_urls_error(client):
    """Test that form shows example for multiple invalid URLs."""
    resp = client.post(
        "/download",
        data={"url": "not-a-valid-url\nanother-bad-url"},
        environ_base=LOCAL,
    )
    assert resp.status_code == 400
    
    html = resp.data.decode("utf-8")
    # Should show example of invalid URL
    assert "Multiple invalid URLs" in html
    assert "not-a-valid-url" in html

def test_playlist_api_returns_all_fields(client):
    """Test that playlist API returns all required fields for editable cards."""
    url = "https://www.youtube.com/playlist?list=PLtest123"
    # Create playlist with specific settings
    resp = client.post(
        "/download",
        json={
            "url": url,
            "category": "test-category",
            "quality": "720",
            "audio_only": True,
            "audio_format": "mp3"
        },
        environ_base=LOCAL
    )
    assert resp.status_code == 202
    
    # Sync it to set last_synced_at
    playlist = client.get("/api/playlists", environ_base=LOCAL).get_json()["items"][0]
    resp = client.post(f"/api/playlists/{playlist['id']}/sync", environ_base=LOCAL)
    assert resp.status_code == 202
    
    # Get updated playlist
    playlists = client.get("/api/playlists", environ_base=LOCAL)
    assert playlists.status_code == 200
    item = playlists.get_json()["items"][0]
    
    # Check all required fields are present
    assert "id" in item
    assert "url" in item
    assert "name" in item
    assert "category" in item
    assert "quality" in item
    assert "audio_only" in item
    assert "audio_format" in item
    assert "last_synced_at" in item
    assert "created_at" in item
    assert "updated_at" in item
    
    # Check specific values
    # When audio_only=True, category is forced to "audio-only"
    assert item["category"] == "audio-only"
    assert item["quality"] == "720"
    # audio_only is stored as integer in database
    assert item["audio_only"] == 1
    assert item["audio_format"] == "mp3"
    assert item["last_synced_at"] is not None  # Should be set after sync


def test_playlist_update_endpoint_exists(client):
    """Test that playlist update endpoint exists and accepts data."""
    url = "https://www.youtube.com/playlist?list=PLupdate123"
    client.post("/download", json={"url": url}, environ_base=LOCAL)
    playlist = client.get("/api/playlists", environ_base=LOCAL).get_json()["items"][0]
    
    # Try to update playlist settings
    resp = client.put(
        f"/api/playlists/{playlist['id']}",
        json={
            "category": "updated-category",
            "quality": "1080",
            "audio_only": False,
            "audio_format": "wav"
        },
        environ_base=LOCAL
    )
    # Now the endpoint should exist
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    
    # Verify the update worked
    updated = client.get("/api/playlists", environ_base=LOCAL).get_json()["items"][0]
    assert updated["category"] == "updated-category"
    assert updated["quality"] == "1080"
    assert updated["audio_only"] == 0  # False
    assert updated["audio_format"] == "wav"


def test_playlist_update_does_not_enqueue_download(client):
    """Test that updating playlist settings doesn't enqueue a download."""
    url = "https://www.youtube.com/playlist?list=PLnodownload123"
    client.post("/download", json={"url": url}, environ_base=LOCAL)
    playlist = client.get("/api/playlists", environ_base=LOCAL).get_json()["items"][0]
    
    # Count jobs before update
    jobs_before = client.get("/api/status", environ_base=LOCAL).get_json()["items"]
    jobs_before_count = len(jobs_before)
    
    # Update playlist settings
    resp = client.put(f"/api/playlists/{playlist['id']}", json={"category": "new-category"}, environ_base=LOCAL)
    assert resp.status_code == 200
    
    # Count jobs after (should be same)
    jobs_after = client.get("/api/status", environ_base=LOCAL).get_json()["items"]
    jobs_after_count = len(jobs_after)
    
    # No new jobs should be created by updating playlist settings
    assert jobs_after_count == jobs_before_count


def test_playlist_sync_uses_updated_settings(client):
    """Test that syncing a playlist uses the updated settings, not original ones."""
    url = "https://www.youtube.com/playlist?list=PLsyncsettings123"
    # Create with initial settings
    client.post(
        "/download",
        json={"url": url, "category": "initial", "quality": "480", "audio_only": False},
        environ_base=LOCAL
    )
    playlist = client.get("/api/playlists", environ_base=LOCAL).get_json()["items"][0]
    
    # Update settings
    resp = client.put(f"/api/playlists/{playlist['id']}", json={"category": "updated", "quality": "1080"}, environ_base=LOCAL)
    assert resp.status_code == 200
    
    # Sync should use updated settings
    resp = client.post(f"/api/playlists/{playlist['id']}/sync", environ_base=LOCAL)
    assert resp.status_code == 202
    
    # Check that job was created with updated settings
    job = client.get("/api/status", environ_base=LOCAL).get_json()["items"][0]
    assert job["category"] == "updated"
    assert job["quality"] == "1080"
