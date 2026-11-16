def test_playlist_can_be_edited_then_synced_without_marking_it_successful(client):
    queued = client.post(
        "/api/jobs",
        json={"url": "https://www.youtube.com/playlist?list=PL_TEST_1"},
        environ_base={"REMOTE_ADDR": "127.0.0.1"},
    )
    assert queued.status_code == 202

    playlists = client.get("/api/playlists", environ_base={"REMOTE_ADDR": "127.0.0.1"})
    assert playlists.status_code == 200
    playlist = playlists.json["items"][0]
    assert playlist["name"] == "PL_TEST_1"
    repo = client.application.extensions["ytpi_repository"]
    first_job_id = queued.json["jobs"][0]["id"]
    repo.update_job(first_job_id, status="finished", stage="Finished")
    repo.set_playlist_sync(playlist["id"], "successful", first_job_id, success=True)
    previous_success = repo.get_playlist(playlist["id"])["last_successful_sync_at"]

    edited = client.put(
        f"/api/playlists/{playlist['id']}",
        json={"category": "Documentaries", "quality": "720", "audio_only": False, "audio_format": "mp3"},
        environ_base={"REMOTE_ADDR": "127.0.0.1"},
    )
    assert edited.status_code == 200
    assert client.get("/api/playlists", environ_base={"REMOTE_ADDR": "127.0.0.1"}).json["items"][0]["category"] == "Documentaries"

    sync = client.post(f"/api/playlists/{playlist['id']}/sync", environ_base={"REMOTE_ADDR": "127.0.0.1"})
    assert sync.status_code == 202
    updated = client.get("/api/playlists", environ_base={"REMOTE_ADDR": "127.0.0.1"}).json["items"][0]
    assert updated["sync_status"] == "requested"
    assert updated["last_successful_sync_at"] == previous_success


def test_playlist_settings_reject_path_traversal(client):
    queued = client.post("/api/jobs", json={"url": "https://www.youtube.com/playlist?list=PL_TEST_2"},
                         environ_base={"REMOTE_ADDR": "127.0.0.1"})
    playlist_id = client.get("/api/playlists", environ_base={"REMOTE_ADDR": "127.0.0.1"}).json["items"][0]["id"]
    response = client.put(f"/api/playlists/{playlist_id}", json={"category": "../outside"},
                          environ_base={"REMOTE_ADDR": "127.0.0.1"})
    assert response.status_code == 400
    assert queued.status_code == 202


def _archive_settings(tmp_path, executable):
    import ipaddress

    from ytpi_app.config import Settings

    return Settings(
        host="127.0.0.1", port=7434, db_path=tmp_path / "data" / "jobs.db", downloads_dir=tmp_path / "downloads",
        allowed_cidrs=(ipaddress.ip_network("127.0.0.1/32"),), trust_proxy=False,
        workers=0, queue_limit=10, timeout_seconds=30, max_retries=0,
        max_output_chars=8000, job_retention_hours=168, max_history_jobs=2000,
        yt_dlp=str(executable), ffmpeg_path="", enable_remote_components=False, block_private_urls=False,
        archive_dir=tmp_path / "data" / "archives",
    )


def test_playlist_jobs_use_download_archive_and_record_stats(tmp_path, monkeypatch):
    from ytpi_app.manager import DownloadManager
    from ytpi_app.repository import JobRepository

    capture = tmp_path / "args.txt"
    executable = tmp_path / "fake-yt-dlp"
    executable.write_text(
        "#!/bin/sh\nprintf '%s\\n' \"$@\" > \"$YTPI_TEST_ARGS\"\n"
        "echo '[youtube:tab] Playlist Mix: Downloading 3 items of 3'\n"
        "echo '[download] one has already been recorded in the archive'\n"
        "echo '[download] two has already been recorded in the archive'\n"
        "echo '__YTPI_TITLE__Three'\n"
    )
    executable.chmod(0o755)
    monkeypatch.setenv("YTPI_TEST_ARGS", str(capture))
    settings = _archive_settings(tmp_path, executable)
    repo = JobRepository(settings.db_path)
    manager = DownloadManager(settings, repo)
    url = "https://www.youtube.com/playlist?list=PLabc123"
    playlist = repo.upsert_playlist(url, "PLabc123", "", "1080", False, "mp3")
    job = manager.enqueue(url, "", "1080", False, "mp3", playlist_id=playlist["id"])
    repo.set_playlist_sync(playlist["id"], "requested", job["id"])

    manager._run(job)
    args = capture.read_text().splitlines()

    archive = tmp_path / "data" / "archives" / "PLabc123.txt"
    assert args[args.index("--download-archive") + 1] == str(archive)
    assert archive.parent.is_dir()
    saved = repo.get_playlist(playlist["id"])
    assert (saved["discovered_count"], saved["already_present_count"]) == (3, 2)
    repo.close()


def test_single_video_jobs_do_not_use_download_archive(tmp_path, monkeypatch):
    from ytpi_app.manager import DownloadManager
    from ytpi_app.repository import JobRepository

    capture = tmp_path / "args.txt"
    executable = tmp_path / "fake-yt-dlp"
    executable.write_text("#!/bin/sh\nprintf '%s\\n' \"$@\" > \"$YTPI_TEST_ARGS\"\n")
    executable.chmod(0o755)
    monkeypatch.setenv("YTPI_TEST_ARGS", str(capture))
    settings = _archive_settings(tmp_path, executable)
    repo = JobRepository(settings.db_path)
    manager = DownloadManager(settings, repo)
    manager._run(manager.enqueue("https://youtu.be/example", "", "1080", False, "mp3"))

    assert "--download-archive" not in capture.read_text().splitlines()
    repo.close()
