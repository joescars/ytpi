import ipaddress
import shlex

import pytest

from ytpi_app.config import Settings, effective_playlist_mode, resolve_playlist_request
from ytpi_app.manager import DownloadManager
from ytpi_app.repository import JobRepository

LOCAL = {"REMOTE_ADDR": "127.0.0.1"}
VIDEO_IN_LIST = "https://www.youtube.com/watch?v=abc123&list=PL_TEST_9&index=3"
PLAYLIST = "https://www.youtube.com/playlist?list=PL_TEST_9"


@pytest.mark.parametrize("url,mode", [
    (VIDEO_IN_LIST, "single"),
    ("https://youtu.be/abc123?list=PL_TEST_9", "single"),
    ("https://www.youtube.com/watch?v=abc123", "single"),
    (PLAYLIST, "playlist"),
    ("https://example.com/?x=list=1", "single"),
])
def test_effective_playlist_mode_parses_the_url(url, mode):
    assert effective_playlist_mode(url) == mode


def test_resolve_playlist_request_only_rewrites_video_plus_list_on_explicit_playlist():
    assert resolve_playlist_request(VIDEO_IN_LIST, "auto") == VIDEO_IN_LIST
    assert resolve_playlist_request(VIDEO_IN_LIST, "playlist") == PLAYLIST
    assert resolve_playlist_request("https://youtu.be/abc123", "playlist") == "https://youtu.be/abc123"
    assert resolve_playlist_request(PLAYLIST, "auto") == PLAYLIST


def test_api_keeps_video_plus_list_as_single_video_by_default(client):
    response = client.post("/api/jobs", json={"url": VIDEO_IN_LIST}, environ_base=LOCAL)
    assert response.status_code == 202
    assert response.json["jobs"][0]["url"] == VIDEO_IN_LIST
    assert client.get("/api/playlists", environ_base=LOCAL).json["items"] == []


def test_api_playlist_mode_requests_the_whole_playlist(client):
    response = client.post("/api/jobs", json={"url": VIDEO_IN_LIST, "playlist_mode": "playlist"}, environ_base=LOCAL)
    assert response.status_code == 202
    assert response.json["jobs"][0]["url"] == PLAYLIST
    assert [item["url"] for item in client.get("/api/playlists", environ_base=LOCAL).json["items"]] == [PLAYLIST]


def test_api_rejects_unknown_playlist_mode(client):
    response = client.post("/api/jobs", json={"url": VIDEO_IN_LIST, "playlist_mode": "bogus"}, environ_base=LOCAL)
    assert response.status_code == 400


def _run_args(tmp_path, url):
    fake = tmp_path / "fake-yt-dlp"
    fake.write_text("#!/bin/sh\nprintf 'ARGS: %s\\n' \"$*\"\n")
    fake.chmod(0o755)
    settings = Settings(
        host="127.0.0.1", port=7434, db_path=tmp_path / "jobs.db", downloads_dir=tmp_path / "downloads",
        allowed_cidrs=(ipaddress.ip_network("127.0.0.1/32"),), trust_proxy=False,
        workers=0, queue_limit=10, timeout_seconds=30, max_retries=0,
        max_output_chars=8000, job_retention_hours=168, max_history_jobs=2000,
        yt_dlp=str(fake), ffmpeg_path="", enable_remote_components=False, block_private_urls=False,
    )
    repository = JobRepository(settings.db_path)
    manager = DownloadManager(settings, repository)
    job = manager.enqueue(url, "", "1080", False, "mp3")
    manager._run(job)
    output = repository.get_job(job["id"])["output"]
    repository.close()
    return shlex.split(output.split("ARGS:", 1)[1].splitlines()[0])


def test_video_plus_list_url_runs_yt_dlp_with_no_playlist(tmp_path):
    args = _run_args(tmp_path, VIDEO_IN_LIST)
    assert "--no-playlist" in args and "--yes-playlist" not in args
    assert "%(title).200B.%(ext)s" in args and "%(playlist).200B/%(title).200B.%(ext)s" not in args
    assert any(arg.startswith("thumbnail:") and "%(playlist).200B" not in arg for arg in args)


def test_playlist_url_runs_yt_dlp_as_full_playlist(tmp_path):
    args = _run_args(tmp_path, PLAYLIST)
    assert "--yes-playlist" in args and "--no-playlist" not in args
    assert "%(playlist).200B/%(title).200B.%(ext)s" in args
    assert any(arg.startswith("thumbnail:") and "%(playlist).200B" in arg for arg in args)


def test_plain_video_url_adds_no_playlist_flag(tmp_path):
    args = _run_args(tmp_path, "https://www.youtube.com/watch?v=abc123")
    assert "--no-playlist" not in args and "--yes-playlist" not in args
