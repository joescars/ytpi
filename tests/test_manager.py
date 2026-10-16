import ipaddress
import threading

from ytpi_app.config import Settings
from ytpi_app.manager import DownloadManager, _parse_progress_line
from ytpi_app.repository import JobRepository


def test_download_command_enables_progress_alongside_print_option(tmp_path):
    fake_yt_dlp = tmp_path / "fake-yt-dlp"
    fake_yt_dlp.write_text("""#!/bin/sh
printf 'ARGS: %s\\n' "$*"
printf '%s\\n' '[download] 43.0% of 12MiB at 1MiB/s ETA 00:10'
sleep 0.1
printf '%s\\n' '[download] 57.5% of 12MiB at unknown ETA unknown'
sleep 0.2
printf '%s\\n' '__YTPI_TITLE__A Great Video'
""")
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
    worker = threading.Thread(target=manager._run, args=(job,))
    worker.start()
    intermediate = None
    while worker.is_alive():
        current = repository.get_job(job["id"])
        if current and current["progress"] == 57.5:
            intermediate = current
            break
    worker.join()
    completed = repository.get_job(job["id"])

    assert intermediate is not None
    assert intermediate["stage"] == "Downloading"
    assert "unknown" in intermediate["speed"]
    assert "unknown" in intermediate["eta"]
    assert "--progress" in completed["output"]
    assert completed["progress"] == 100
    repository.close()


def test_progress_parser_accepts_percent_without_speed_or_eta():
    assert _parse_progress_line("[download] 57.5% of 12MiB") == {
        "progress": 57.5, "speed": "", "eta": ""
    }


def test_progress_parser_accepts_unknown_speed_and_eta():
    assert _parse_progress_line("[download] 57.5% at unknown ETA unknown") == {
        "progress": 57.5, "speed": "unknown", "eta": "unknown"
    }


def test_progress_parser_accepts_completion_line_without_eta():
    assert _parse_progress_line("[download] 100% of 20MiB in 00:01:20 at 255.24KiB/s") == {
        "progress": 100, "speed": "255.24KiB/s", "eta": ""
    }


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
