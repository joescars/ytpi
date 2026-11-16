import ipaddress

from ytpi_app.config import Settings
from ytpi_app.manager import DownloadManager
from ytpi_app.repository import JobRepository


def test_auto_subtitles_are_not_requested_by_default(tmp_path, monkeypatch):
    capture = tmp_path / "yt-dlp-args.txt"
    executable = tmp_path / "fake-yt-dlp"
    executable.write_text(
        "#!/bin/sh\nprintf '%s\\n' \"$@\" > \"$YTPI_TEST_ARGS\"\nprintf '%s\\n' '__YTPI_TITLE__Complete video'\n"
    )
    executable.chmod(0o755)
    monkeypatch.setenv("YTPI_TEST_ARGS", str(capture))
    settings = Settings(
        host="127.0.0.1", port=7434, db_path=tmp_path / "jobs.db", downloads_dir=tmp_path / "downloads",
        allowed_cidrs=(ipaddress.ip_network("127.0.0.1/32"),), trust_proxy=False,
        workers=0, queue_limit=10, timeout_seconds=30, max_retries=0,
        max_output_chars=8000, job_retention_hours=168, max_history_jobs=2000,
        yt_dlp=str(executable), ffmpeg_path="", enable_remote_components=False, block_private_urls=False,
    )
    repo = JobRepository(settings.db_path)
    manager = DownloadManager(settings, repo)
    job = manager.enqueue("https://youtu.be/example", "", "1080", False, "mp3")

    manager._run(job)
    args = capture.read_text().splitlines()

    assert "--write-auto-subs" not in args
    assert "--sub-langs" not in args
    assert repo.get_job(job["id"])["status"] == "finished"
    repo.close()


def test_auto_subtitles_can_be_enabled_explicitly(tmp_path, monkeypatch):
    capture = tmp_path / "yt-dlp-args.txt"
    executable = tmp_path / "fake-yt-dlp"
    executable.write_text(
        "#!/bin/sh\nprintf '%s\\n' \"$@\" > \"$YTPI_TEST_ARGS\"\nprintf '%s\\n' '__YTPI_TITLE__Complete video'\n"
    )
    executable.chmod(0o755)
    monkeypatch.setenv("YTPI_TEST_ARGS", str(capture))
    settings = Settings(
        host="127.0.0.1", port=7434, db_path=tmp_path / "jobs.db", downloads_dir=tmp_path / "downloads",
        allowed_cidrs=(ipaddress.ip_network("127.0.0.1/32"),), trust_proxy=False,
        workers=0, queue_limit=10, timeout_seconds=30, max_retries=0,
        max_output_chars=8000, job_retention_hours=168, max_history_jobs=2000,
        yt_dlp=str(executable), ffmpeg_path="", enable_remote_components=False,
        block_private_urls=False, write_auto_subs=True,
    )
    repo = JobRepository(settings.db_path)
    manager = DownloadManager(settings, repo)
    job = manager.enqueue("https://youtu.be/example", "", "1080", False, "mp3")

    manager._run(job)
    args = capture.read_text().splitlines()

    assert "--write-auto-subs" in args
    assert "--sub-langs" in args
    repo.close()


def _run_and_capture_args(tmp_path, monkeypatch, url, **overrides):
    capture = tmp_path / "yt-dlp-args.txt"
    executable = tmp_path / "fake-yt-dlp"
    executable.write_text(
        "#!/bin/sh\nprintf '%s\\n' \"$@\" > \"$YTPI_TEST_ARGS\"\nprintf '%s\\n' '__YTPI_TITLE__Complete video'\n"
    )
    executable.chmod(0o755)
    monkeypatch.setenv("YTPI_TEST_ARGS", str(capture))
    settings = Settings(
        host="127.0.0.1", port=7434, db_path=tmp_path / "jobs.db", downloads_dir=tmp_path / "downloads",
        allowed_cidrs=(ipaddress.ip_network("127.0.0.1/32"),), trust_proxy=False,
        workers=0, queue_limit=10, timeout_seconds=30, max_retries=0,
        max_output_chars=8000, job_retention_hours=168, max_history_jobs=2000,
        yt_dlp=str(executable), ffmpeg_path="", enable_remote_components=False,
        block_private_urls=False, **overrides,
    )
    repo = JobRepository(settings.db_path)
    manager = DownloadManager(settings, repo)
    job = manager.enqueue(url, "", "1080", False, "mp3")
    manager._run(job)
    args = capture.read_text().splitlines()
    repo.close()
    return args


def test_output_templates_bound_title_bytes_and_match_thumbnail(tmp_path, monkeypatch):
    args = _run_and_capture_args(tmp_path, monkeypatch, "https://youtu.be/example")

    assert args[args.index("-o") + 1] == "%(title).200B.%(ext)s"
    thumbnail = args[args.index("--output") + 1]
    assert thumbnail == f"thumbnail:{tmp_path / 'downloads'}/%(title).200B-thumb.%(ext)s"


def test_playlist_templates_bound_playlist_and_title_with_custom_cap(tmp_path, monkeypatch):
    args = _run_and_capture_args(tmp_path, monkeypatch, "https://www.youtube.com/playlist?list=PL123",
                                 max_filename_bytes=120)

    assert args[args.index("-o") + 1] == "%(playlist).120B/%(title).120B.%(ext)s"
    assert args[args.index("--output") + 1].endswith("/%(playlist).120B/%(title).120B-thumb.%(ext)s")


def test_ffmpeg_strict_flag_is_off_by_default_and_opt_in(tmp_path, monkeypatch):
    assert "--postprocessor-args" not in _run_and_capture_args(tmp_path, monkeypatch, "https://youtu.be/example")
    args = _run_and_capture_args(tmp_path, monkeypatch, "https://youtu.be/example", ffmpeg_strict_experimental=True)
    assert args[args.index("--postprocessor-args") + 1] == "ffmpeg:-strict -2"
