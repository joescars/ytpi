import importlib
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture
def client(tmp_path, monkeypatch):
    downloads = tmp_path / "downloads"
    downloads.mkdir()
    db_path = tmp_path / "jobs.db"

    monkeypatch.setenv("YTPI_DOWNLOADS_DIR", str(downloads))
    monkeypatch.setenv("YTPI_DB_PATH", str(db_path))
    monkeypatch.setenv("YTPI_MAX_WORKERS", "0")
    monkeypatch.setenv("YTPI_ALLOWED_CIDRS", "127.0.0.0/8")

    import app as app_module

    importlib.reload(app_module)
    flask_app = app_module.create_app()
    flask_app.config["TESTING"] = True

    with flask_app.test_client() as test_client:
        yield test_client


def test_healthz(client):
    resp = client.get("/healthz", environ_base={"REMOTE_ADDR": "127.0.0.1"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "ok"


def test_blocks_non_local_ip(client):
    resp = client.get("/", environ_base={"REMOTE_ADDR": "8.8.8.8"})
    assert resp.status_code == 403


def test_rejects_path_traversal_category(client):
    resp = client.post(
        "/download",
        json={"url": "https://youtube.com/watch?v=abc123", "category": "../../etc"},
        environ_base={"REMOTE_ADDR": "127.0.0.1"},
    )
    assert resp.status_code == 400


def test_enqueue_download(client):
    resp = client.post(
        "/download",
        json={"url": "https://youtube.com/watch?v=abc123", "quality": "720", "category": "Music"},
        environ_base={"REMOTE_ADDR": "127.0.0.1"},
    )
    assert resp.status_code == 202
    data = resp.get_json()
    assert "job_id" in data

    status_resp = client.get("/api/status", environ_base={"REMOTE_ADDR": "127.0.0.1"})
    assert status_resp.status_code == 200
    status_data = status_resp.get_json()
    assert status_data["total"] >= 1


def test_enqueue_audio_only_mp3(client):
    resp = client.post(
        "/download",
        json={
            "url": "https://youtube.com/watch?v=abc123",
            "audio_only": "true",
            "audio_format": "mp3",
            "category": "Music",
        },
        environ_base={"REMOTE_ADDR": "127.0.0.1"},
    )
    assert resp.status_code == 202
    data = resp.get_json()
    assert "job_id" in data

    # Verify the job was stored with audio_only=1 and audio_format="mp3"
    status_resp = client.get("/api/status", environ_base={"REMOTE_ADDR": "127.0.0.1"})
    items = status_resp.get_json()["items"]
    job = next(j for j in items if j["id"] == data["job_id"])
    assert job["audio_only"] == 1
    assert job["audio_format"] == "mp3"


def test_enqueue_audio_only_wav(client):
    resp = client.post(
        "/download",
        json={
            "url": "https://youtube.com/watch?v=abc123",
            "audio_only": "true",
            "audio_format": "wav",
        },
        environ_base={"REMOTE_ADDR": "127.0.0.1"},
    )
    assert resp.status_code == 202
    data = resp.get_json()
    assert "job_id" in data

    status_resp = client.get("/api/status", environ_base={"REMOTE_ADDR": "127.0.0.1"})
    items = status_resp.get_json()["items"]
    job = next(j for j in items if j["id"] == data["job_id"])
    assert job["audio_only"] == 1
    assert job["audio_format"] == "wav"


def test_enqueue_audio_only_invalid_format_defaults_to_mp3(client):
    resp = client.post(
        "/download",
        json={
            "url": "https://youtube.com/watch?v=abc123",
            "audio_only": "true",
            "audio_format": "flac",
        },
        environ_base={"REMOTE_ADDR": "127.0.0.1"},
    )
    assert resp.status_code == 202
    data = resp.get_json()
    assert "job_id" in data

    status_resp = client.get("/api/status", environ_base={"REMOTE_ADDR": "127.0.0.1"})
    items = status_resp.get_json()["items"]
    job = next(j for j in items if j["id"] == data["job_id"])
    assert job["audio_only"] == 1
    assert job["audio_format"] == "mp3"


def test_enqueue_without_audio_only_is_false(client):
    resp = client.post(
        "/download",
        json={"url": "https://youtube.com/watch?v=abc123", "quality": "1080"},
        environ_base={"REMOTE_ADDR": "127.0.0.1"},
    )
    assert resp.status_code == 202
    data = resp.get_json()

    status_resp = client.get("/api/status", environ_base={"REMOTE_ADDR": "127.0.0.1"})
    items = status_resp.get_json()["items"]
    job = next(j for j in items if j["id"] == data["job_id"])
    assert job["audio_only"] == 0
