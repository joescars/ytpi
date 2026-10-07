def test_download_details_show_filename_for_completed_job(tmp_path, monkeypatch):
    from ytpi_app import create_app

    monkeypatch.setenv("YTPI_DB_PATH", str(tmp_path / "jobs.sqlite3"))
    monkeypatch.setenv("YTPI_DOWNLOADS_DIR", str(tmp_path / "downloads"))
    monkeypatch.setenv("YTPI_ALLOWED_CIDRS", "127.0.0.1/32")
    monkeypatch.setenv("YTPI_MAX_WORKERS", "0")
    app = create_app()
    app.config.update(TESTING=True)
    client = app.test_client()
    try:
        queued = client.post("/api/jobs", json={"url": "https://youtu.be/example", "quality": "1080"},
                             environ_base={"REMOTE_ADDR": "127.0.0.1"})
        job_id = queued.json["jobs"][0]["id"]
        repository = app.extensions["ytpi_repository"]
        repository.update_job(job_id, title="A Finished Clip", status="finished", stage="Finished", progress=100,
                              filename="/app/downloads/A Finished Clip.mp4")

        detail = client.get(f"/api/jobs/{job_id}", environ_base={"REMOTE_ADDR": "127.0.0.1"})

        assert detail.json["filename"] == "/app/downloads/A Finished Clip.mp4"
        assert detail.json["status"] == "finished"
    finally:
        app.extensions["ytpi_repository"].close()
        app.extensions["ytpi_manager"].shutdown()
