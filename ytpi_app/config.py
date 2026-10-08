from __future__ import annotations

import ipaddress
import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse


DEFAULT_CIDRS = "127.0.0.0/8,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16,::1/128"
QUALITIES = {"max", "2160", "1440", "1080", "720", "480"}
AUDIO_FORMATS = {"mp3", "wav"}


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


def _integer(name: str, default: int, minimum: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError:
        return default
    return max(value, minimum)


def load_settings() -> Settings:
    cidrs = tuple(
        ipaddress.ip_network(value.strip(), strict=False)
        for value in os.getenv("YTPI_ALLOWED_CIDRS", DEFAULT_CIDRS).split(",")
        if value.strip()
    )
    return Settings(
        host=os.getenv("YTPI_HOST", "0.0.0.0"),
        port=_integer("YTPI_PORT", 7434, 1),
        db_path=Path(os.getenv("YTPI_DB_PATH", "./data/jobs.db")).resolve(),
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
