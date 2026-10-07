import ipaddress

from ytpi_app.config import Settings
from ytpi_app.manager import DownloadManager
from ytpi_app.repository import JobRepository


def test_manager_persists_title_and_completes_a_download(tmp_path):
    fake_yt_dlp = tmp_path / "fake-yt-dlp"
    fake_yt_dlp.write_text(
        "#!/bin/sh\nprintf '%s\\n' '[download] 43.0% of 12MiB at 1MiB/s ETA 00:10' '[download] Destination: /media/A Great Video.webm' '[Merger] Merging formats into \\\"/media/A Great Video.mp4\\\"' '__YTPI_TITLE__A Great Video'\n"
    )
    fake_yt_dlp.chmod(0o755)
    settings = Settings(
        host="127.0.0.1", port=7434, db_path=tmp_path / "jobs.db", downloads_dir=tmp_path / "downloads",
        allowed_cidrs=(ipaddress.ip_network("127.0.0.1/32"),), trust_proxy=False,
        workers=0, queue_limit=10, timeout_seconds=30, max_retries=0,
        max_output_chars=8000, job_retention_hours=168, max_history_jobs=2000,
        yt_dlp=str(fake_yt_dlp), ffmpeg_path="", enable_remote_components=False, block_private_urls=False,
    )
    repository = JobRepository(settings.db_path)
    manager = DownloadManager(settings, repository)
    job = manager.enqueue("https://youtu.be/example", "", "1080", False, "mp3")

    manager._run(job)
    completed = repository.get_job(job["id"])

    assert completed["status"] == "finished"
    assert completed["title"] == "A Great Video"
    assert completed["progress"] == 100
    assert completed["filename"] == "/media/A Great Video.webm"
    assert "43.0%" in completed["output"]
    repository.close()


def test_failed_download_retries_once_then_succeeds(tmp_path):
    fake_yt_dlp = tmp_path / "fake-yt-dlp"
    fake_yt_dlp.write_text("#!/bin/sh\necho 'temporary network error'\nexit 1\n")
    fake_yt_dlp.chmod(0o755)
    settings = Settings(
        host="127.0.0.1", port=7434, db_path=tmp_path / "retry.db", downloads_dir=tmp_path / "downloads",
        allowed_cidrs=(ipaddress.ip_network("127.0.0.1/32"),), trust_proxy=False,
        workers=0, queue_limit=10, timeout_seconds=30, max_retries=1,
        max_output_chars=8000, job_retention_hours=168, max_history_jobs=2000,
        yt_dlp=str(fake_yt_dlp), ffmpeg_path="", enable_remote_components=False, block_private_urls=False,
    )
    repository = JobRepository(settings.db_path)
    manager = DownloadManager(settings, repository)
    job = manager.enqueue("https://youtu.be/retry", "", "max", False, "mp3")

    manager._run(job)
    retrying = repository.get_job(job["id"])
    assert retrying["status"] == "queued"
    assert retrying["attempt_count"] == 1
    assert "Retrying (1/1)" in retrying["error"]

    fake_yt_dlp.write_text("#!/bin/sh\nprintf '%s\\n' '__YTPI_TITLE__Recovered title'\n")
    manager._run(retrying)
    completed = repository.get_job(job["id"])
    assert completed["status"] == "finished"
    assert completed["attempt_count"] == 2
    assert completed["title"] == "Recovered title"
    repository.close()


def test_successful_download_records_finalized_filename_from_merger_output(tmp_path):
    fake_yt_dlp = tmp_path / "fake-yt-dlp"
    fake_yt_dlp.write_text(
        "#!/bin/sh\nprintf '%s\\n' '[download] Destination: /media/Final Video.f137.mp4' '[Merger] Merging formats into \"/media/Final Video.mp4\"' '__YTPI_TITLE__Final Video'\n"
    )
    fake_yt_dlp.chmod(0o755)
    settings = Settings(
        host="127.0.0.1", port=7434, db_path=tmp_path / "finalized.db", downloads_dir=tmp_path / "downloads",
        allowed_cidrs=(ipaddress.ip_network("127.0.0.1/32"),), trust_proxy=False,
        workers=0, queue_limit=10, timeout_seconds=30, max_retries=0,
        max_output_chars=8000, job_retention_hours=168, max_history_jobs=2000,
        yt_dlp=str(fake_yt_dlp), ffmpeg_path="", enable_remote_components=False, block_private_urls=False,
    )
    repository = JobRepository(settings.db_path)
    manager = DownloadManager(settings, repository)
    job = manager.enqueue("https://youtu.be/finalized", "", "1080", False, "mp3")

    manager._run(job)
    finished = repository.get_job(job["id"])

    assert finished["status"] == "finished"
    assert finished["filename"] == "/media/Final Video.mp4"
    repository.close()
