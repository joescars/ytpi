import ipaddress

import pytest

from ytpi_app import manager as manager_module
from ytpi_app.config import Settings, load_settings
from ytpi_app.manager import DownloadManager, detect_rate_limit
from ytpi_app.repository import JobRepository


class FakeProcess:
    pid = 0

    def __init__(self, lines, returncode=1):
        self.stdout = iter(lines)
        self.returncode = returncode

    def wait(self, timeout=None):
        return self.returncode

    def poll(self):
        return self.returncode


def make_manager(tmp_path, **overrides):
    tmp_path.mkdir(parents=True, exist_ok=True)
    settings = Settings(
        host="127.0.0.1", port=7434, db_path=tmp_path / "jobs.db", downloads_dir=tmp_path / "downloads",
        allowed_cidrs=(ipaddress.ip_network("127.0.0.1/32"),), trust_proxy=False,
        workers=0, queue_limit=10, timeout_seconds=30, max_retries=overrides.pop("max_retries", 1),
        max_output_chars=8000, job_retention_hours=168, max_history_jobs=2000,
        yt_dlp="yt-dlp", ffmpeg_path="", enable_remote_components=False, block_private_urls=False, **overrides,
    )
    repo = JobRepository(settings.db_path)
    return DownloadManager(settings, repo), repo


@pytest.mark.parametrize("line,expected", [
    ("ERROR: unable to download video data: HTTP Error 429: Too Many Requests", "429"),
    ("ERROR: unable to download webpage: HTTP Error 402: Payment Required", "402"),
    ("ERROR: unable to download video data: HTTP Error 403: Forbidden", "403"),
    ("ERROR: something else entirely", None),
])
def test_detect_rate_limit(line, expected):
    assert detect_rate_limit(["[youtube] x: Downloading webpage", line]) == expected


def test_429_backs_off_before_retry_then_reports_actionable_error(tmp_path, monkeypatch):
    sleeps = []
    monkeypatch.setattr(manager_module.time, "sleep", sleeps.append)
    monkeypatch.setattr(manager_module.random, "uniform", lambda low, high: 1.0)
    line = "ERROR: unable to download video data: HTTP Error 429: Too Many Requests"
    monkeypatch.setattr(manager_module.subprocess, "Popen", lambda *args, **kwargs: FakeProcess([line + "\n"]))
    manager, repo = make_manager(tmp_path, rate_limit_backoff_seconds=3, rate_limit_backoff_cap_seconds=60)
    try:
        job = manager.enqueue("https://youtu.be/example", "", "1080")
        manager._run(job)

        retrying = repo.get_job(job["id"])
        assert retrying["status"] == "queued"
        assert retrying["stage"] == "Backing off"
        assert "rate-limiting" in retrying["error"]
        assert sum(sleeps) == pytest.approx(3)

        manager._run(retrying)
        failed = repo.get_job(job["id"])
        assert failed["status"] == "error"
        assert "HTTP 429" in failed["error"]
        assert "retry later" in failed["error"].lower()
        assert line in failed["error"]
    finally:
        repo.close()


def test_non_rate_limit_failure_retries_without_backoff(tmp_path, monkeypatch):
    sleeps = []
    monkeypatch.setattr(manager_module.time, "sleep", sleeps.append)
    monkeypatch.setattr(manager_module.subprocess, "Popen", lambda *args, **kwargs: FakeProcess(["ERROR: boom\n"]))
    manager, repo = make_manager(tmp_path)
    try:
        job = manager.enqueue("https://youtu.be/example", "", "1080")
        manager._run(job)
        assert repo.get_job(job["id"])["stage"] == "Retry scheduled"
        assert sleeps == []
    finally:
        repo.close()


def test_backoff_grows_and_is_capped(tmp_path):
    manager, repo = make_manager(tmp_path, rate_limit_backoff_seconds=10, rate_limit_backoff_cap_seconds=30)
    try:
        assert all(7.5 <= manager._rate_limit_delay(1) <= 12.5 for _ in range(20))
        assert all(manager._rate_limit_delay(5) <= 30 for _ in range(20))
    finally:
        repo.close()
    manager, repo = make_manager(tmp_path / "off", rate_limit_backoff_seconds=0)
    try:
        assert manager._rate_limit_delay(1) == 0
    finally:
        repo.close()


def test_optional_flags_are_off_by_default_and_wired_when_set(tmp_path, monkeypatch):
    commands = []

    def fake_popen(command, **kwargs):
        commands.append(command)
        return FakeProcess([], returncode=0)

    monkeypatch.setattr(manager_module.subprocess, "Popen", fake_popen)
    manager, repo = make_manager(tmp_path)
    try:
        manager._run(manager.enqueue("https://youtu.be/example", "", "1080"))
    finally:
        repo.close()
    for flag in ("--cookies", "--user-agent", "--source-address", "--min-sleep-interval", "--sleep-requests"):
        assert flag not in commands[0]

    manager, repo = make_manager(tmp_path / "on", cookies_file="/app/data/cookies.txt", user_agent="Mozilla/5.0 Test",
                                 source_address="203.0.113.5", min_sleep_interval=2, sleep_requests=1.5)
    try:
        manager._run(manager.enqueue("https://youtu.be/example", "", "1080"))
    finally:
        repo.close()
    command = commands[1]
    assert command[command.index("--cookies") + 1] == "/app/data/cookies.txt"
    assert command[command.index("--user-agent") + 1] == "Mozilla/5.0 Test"
    assert command[command.index("--source-address") + 1] == "203.0.113.5"
    assert command[command.index("--min-sleep-interval") + 1] == "2"
    assert command[command.index("--sleep-requests") + 1] == "1.5"


def test_settings_default_off_and_read_env(monkeypatch):
    for name in ("YTPI_COOKIES_FILE", "YTPI_USER_AGENT", "YTPI_SOURCE_ADDRESS", "YTPI_MIN_SLEEP_INTERVAL", "YTPI_SLEEP_REQUESTS"):
        monkeypatch.delenv(name, raising=False)
    settings = load_settings()
    assert (settings.cookies_file, settings.user_agent, settings.source_address) == ("", "", "")
    assert settings.min_sleep_interval == 0 and settings.sleep_requests == 0
    monkeypatch.setenv("YTPI_COOKIES_FILE", "/app/data/cookies.txt")
    monkeypatch.setenv("YTPI_SLEEP_REQUESTS", "1.5")
    settings = load_settings()
    assert settings.cookies_file == "/app/data/cookies.txt" and settings.sleep_requests == 1.5
