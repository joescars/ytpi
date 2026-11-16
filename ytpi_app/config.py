from __future__ import annotations

import hashlib
import ipaddress
import os
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import parse_qs, quote, urlparse


DEFAULT_CIDRS = "127.0.0.0/8,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16,::1/128"
QUALITIES = {"max", "2160", "1440", "1080", "720", "480"}
AUDIO_FORMATS = {"mp3", "wav"}
PLAYLIST_MODES = {"auto", "playlist"}
YOUTUBE_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com"}


@dataclass(frozen=True)
class Settings:
    host: str
    port: int
    db_path: Path
    downloads_dir: Path
    allowed_cidrs: tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...]
    trust_proxy: bool
    workers: int
    queue_limit: int
    timeout_seconds: int
    max_retries: int
    max_output_chars: int
    job_retention_hours: int
    max_history_jobs: int
    yt_dlp: str
    ffmpeg_path: str
    enable_remote_components: bool
    block_private_urls: bool
    write_auto_subs: bool = False
    max_filename_bytes: int = 200
    ffmpeg_strict_experimental: bool = False
    archive_dir: Path | None = None
    # Optional yt-dlp anti-block settings; all off by default.
    cookies_file: str = ""
    user_agent: str = ""
    source_address: str = ""
    min_sleep_interval: float = 0
    sleep_requests: float = 0
    # Jittered backoff before retrying 429/402/403 failures (seconds; 0 disables).
    rate_limit_backoff_seconds: int = 5
    rate_limit_backoff_cap_seconds: int = 60


def _integer(name: str, default: int, minimum: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError:
        return default
    return max(value, minimum)


def playlist_archive_key(url: str) -> str:
    """Return a filesystem-safe archive name for a playlist URL's ``list=`` id, or "" for non-playlist URLs."""
    playlist_id = parse_qs(urlparse(url).query).get("list", [""])[0].strip()
    if not playlist_id:
        return ""
    key = re.sub(r"[^A-Za-z0-9_-]", "_", playlist_id)[:100]
    if key != playlist_id:
        key = f"{key}-{hashlib.sha1(playlist_id.encode()).hexdigest()[:10]}"
    return key


def _number(name: str, default: float, minimum: float) -> float:
    try:
        value = float(os.getenv(name, str(default)))
    except ValueError:
        return default
    return max(value, minimum) if value == value else default


def load_settings() -> Settings:
    db_path = Path(os.getenv("YTPI_DB_PATH", "./data/jobs.db")).resolve()
    cidrs = tuple(
        ipaddress.ip_network(value.strip(), strict=False)
        for value in os.getenv("YTPI_ALLOWED_CIDRS", DEFAULT_CIDRS).split(",")
        if value.strip()
    )
    return Settings(
        host=os.getenv("YTPI_HOST", "0.0.0.0"),
        port=_integer("YTPI_PORT", 7434, 1),
        db_path=db_path,
        downloads_dir=Path(os.getenv("YTPI_DOWNLOADS_DIR", "./downloads")).resolve(),
        allowed_cidrs=cidrs,
        trust_proxy=os.getenv("YTPI_TRUST_PROXY", "0").lower() in {"1", "true", "yes", "on"},
        workers=_integer("YTPI_MAX_WORKERS", 1, 0),
        queue_limit=_integer("YTPI_MAX_QUEUE_SIZE", 200, 1),
        timeout_seconds=_integer("YTPI_JOB_TIMEOUT_SECONDS", 3600, 30),
        max_retries=_integer("YTPI_MAX_RETRIES", 1, 0),
        max_output_chars=_integer("YTPI_MAX_OUTPUT_CHARS", 8000, 1000),
        job_retention_hours=_integer("YTPI_JOB_RETENTION_HOURS", 168, 1),
        max_history_jobs=_integer("YTPI_MAX_HISTORY_JOBS", 2000, 100),
        yt_dlp=os.getenv("YTPI_YTDLP_BIN", "yt-dlp"),
        ffmpeg_path=os.getenv("YTPI_FFMPEG_PATH", ""),
        enable_remote_components=os.getenv("YTPI_ENABLE_REMOTE_COMPONENTS", "1").lower() not in {"0", "false", "no", "off"},
        block_private_urls=os.getenv("YTPI_BLOCK_PRIVATE_URLS", "0").lower() in {"1", "true", "yes", "on"},
        write_auto_subs=os.getenv("YTPI_WRITE_AUTO_SUBS", "0").lower() in {"1", "true", "yes", "on"},
        max_filename_bytes=_integer("YTPI_MAX_FILENAME_BYTES", 200, 20),
        ffmpeg_strict_experimental=os.getenv("YTPI_FFMPEG_STRICT_EXPERIMENTAL", "0").lower() in {"1", "true", "yes", "on"},
        archive_dir=Path(os.getenv("YTPI_ARCHIVE_DIR", str(db_path.parent / "archives"))).resolve(),
        cookies_file=os.getenv("YTPI_COOKIES_FILE", "").strip(),
        user_agent=os.getenv("YTPI_USER_AGENT", "").strip(),
        source_address=os.getenv("YTPI_SOURCE_ADDRESS", "").strip(),
        min_sleep_interval=_number("YTPI_MIN_SLEEP_INTERVAL", 0, 0),
        sleep_requests=_number("YTPI_SLEEP_REQUESTS", 0, 0),
        rate_limit_backoff_seconds=_integer("YTPI_RATE_LIMIT_BACKOFF_SECONDS", 5, 0),
        rate_limit_backoff_cap_seconds=_integer("YTPI_RATE_LIMIT_BACKOFF_CAP_SECONDS", 60, 0),
    )


def client_allowed(remote_addr: str | None, forwarded_for: str, settings: Settings) -> bool:
    address = remote_addr or ""
    if settings.trust_proxy and forwarded_for:
        address = forwarded_for.split(",", 1)[0].strip()
    try:
        client_ip = ipaddress.ip_address(address)
    except ValueError:
        return False
    return any(client_ip.version == network.version and client_ip in network for network in settings.allowed_cidrs)


def safe_category(raw: str) -> str:
    value = " ".join((raw or "").strip().split())
    if not value or value in {".", ".."} or "/" in value or "\\" in value or ".." in value:
        raise ValueError("Choose a valid category name.")
    value = "".join(character for character in value if character.isalnum() or character in " _.-")
    value = value.strip(" .")[:80]
    if not value:
        raise ValueError("Choose a valid category name.")
    return value


def valid_media_url(value: str, block_private: bool = False) -> bool:
    try:
        parsed = urlparse(value.strip())
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            return False
        if block_private:
            try:
                ip = ipaddress.ip_address(parsed.hostname)
            except ValueError:
                return True
            return not (ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast)
        return True
    except ValueError:
        return False


def youtube_ids(url: str) -> tuple[str, str]:
    """Return (video_id, playlist_id) parsed from a URL's host, path, and query; either may be empty."""
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    values = parse_qs(parsed.query)
    playlist_id = values.get("list", [""])[0].strip()
    path = parsed.path.rstrip("/")
    if host in YOUTUBE_HOSTS:
        return (values.get("v", [""])[0].strip() if path == "/watch" else ""), playlist_id
    if host == "youtu.be":
        return path.lstrip("/"), playlist_id
    return "", playlist_id


def effective_playlist_mode(url: str) -> str:
    """Return "single" or "playlist". A link that names a video (watch?v=...&list=...) is one video; a bare list= link is a playlist."""
    video_id, playlist_id = youtube_ids(url)
    return "single" if video_id or not playlist_id else "playlist"


def resolve_playlist_request(url: str, requested: str = "auto") -> str:
    """Apply the per-request playlist choice by rewriting a video+list link to its canonical playlist URL.

    With "auto" the URL is untouched (video+list stays a single video); with "playlist" a
    watch?v=...&list=... link becomes https://www.youtube.com/playlist?list=... so the intent is
    carried by the URL itself (retries, restarts, and saved playlists all agree).
    """
    video_id, playlist_id = youtube_ids(url)
    if requested == "playlist" and video_id and playlist_id:
        return f"https://www.youtube.com/playlist?list={quote(playlist_id, safe='')}"
    return url
