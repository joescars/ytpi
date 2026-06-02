import ipaddress
import json
import logging
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse

DEFAULT_ALLOWED_CIDRS = "127.0.0.0/8,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16,::1/128"
ALLOWED_QUALITIES = {"max", "2160", "1440", "1080", "720", "480"}
ALLOWED_AUDIO_FORMATS = {"mp3", "wav"}
AUDIO_ONLY_CATEGORY = "audio-only"


@dataclass
class Config:
    host: str
    port: int
    downloads_dir: Path
    db_path: Path
    allowed_cidrs: list[ipaddress._BaseNetwork]
    trust_proxy: bool
    enable_share_get: bool
    share_token: str
    max_queue_size: int
    max_workers: int
    job_timeout_seconds: int
    max_retries: int
    max_output_chars: int
    job_retention_hours: int
    max_history_jobs: int
    ffmpeg_path: str
    yt_dlp_binary: str


def parse_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def parse_int(value: str | None, default: int, min_value: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(parsed, min_value)


def parse_cidrs(value: str | None) -> list[ipaddress._BaseNetwork]:
    cidrs: list[ipaddress._BaseNetwork] = []
    for entry in (value or DEFAULT_ALLOWED_CIDRS).split(","):
        item = entry.strip()
        if not item:
            continue
        cidrs.append(ipaddress.ip_network(item, strict=False))
    return cidrs


class JsonLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if hasattr(record, "context") and isinstance(record.context, dict):
            payload.update(record.context)
        return json.dumps(payload, ensure_ascii=True)


def setup_logging() -> logging.Logger:
    logger = logging.getLogger("ytpi")
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler()
    handler.setFormatter(JsonLogFormatter())
    logger.addHandler(handler)
    return logger


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_config() -> Config:
    downloads_dir = Path(os.getenv("YTPI_DOWNLOADS_DIR", "./downloads")).resolve()
    db_path = Path(os.getenv("YTPI_DB_PATH", "./jobs.db")).resolve()
    return Config(
        host=os.getenv("YTPI_HOST", "0.0.0.0"),
        port=parse_int(os.getenv("YTPI_PORT", "7434"), 7434, 1),
        downloads_dir=downloads_dir,
        db_path=db_path,
        allowed_cidrs=parse_cidrs(os.getenv("YTPI_ALLOWED_CIDRS", DEFAULT_ALLOWED_CIDRS)),
        trust_proxy=parse_bool(os.getenv("YTPI_TRUST_PROXY", "0")),
        enable_share_get=parse_bool(os.getenv("YTPI_ENABLE_SHARE_GET", "1")),
        share_token=os.getenv("YTPI_SHARE_TOKEN", "").strip(),
        max_queue_size=parse_int(os.getenv("YTPI_MAX_QUEUE_SIZE", "200"), 200, 1),
        max_workers=parse_int(os.getenv("YTPI_MAX_WORKERS", "1"), 1, 0),
        job_timeout_seconds=parse_int(os.getenv("YTPI_JOB_TIMEOUT_SECONDS", "3600"), 3600, 30),
        max_retries=parse_int(os.getenv("YTPI_MAX_RETRIES", "1"), 1, 0),
        max_output_chars=parse_int(os.getenv("YTPI_MAX_OUTPUT_CHARS", "8000"), 8000, 1000),
        job_retention_hours=parse_int(os.getenv("YTPI_JOB_RETENTION_HOURS", "168"), 168, 1),
        max_history_jobs=parse_int(os.getenv("YTPI_MAX_HISTORY_JOBS", "2000"), 2000, 100),
        ffmpeg_path=os.getenv("YTPI_FFMPEG_PATH", ""),
        yt_dlp_binary=os.getenv("YTPI_YTDLP_BIN", "yt-dlp"),
    )


def validate_quality(quality: str) -> str:
    if not quality or quality not in ALLOWED_QUALITIES:
        return "max"
    return quality


def validate_audio_format(audio_format: str) -> str:
    if not audio_format or audio_format not in ALLOWED_AUDIO_FORMATS:
        return "mp3"
    return audio_format


def normalize_urls(urls_input: Any) -> list[str]:
    if isinstance(urls_input, str):
        parts = re.split(r"[\n,]+", urls_input)
        urls = [part.strip() for part in parts if part and part.strip()]
    elif isinstance(urls_input, list):
        urls = [str(url).strip() for url in urls_input if str(url).strip()]
    else:
        return []
    return urls


def validate_url(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return False
    return bool(parsed.netloc)


def sanitize_category(raw: str) -> str:
    value = (raw or "").strip()
    if not value:
        return ""
    value = value.replace("/", "-").replace("\\", "-")
    value = re.sub(r"\s+", " ", value)
    value = re.sub(r"[^A-Za-z0-9 _.-]", "", value)
    value = value.strip(" .")
    return value[:80]


def normalize_category_input(raw: str) -> str:
    source = (raw or "").strip()
    if not source:
        return ""
    if ".." in source or "/" in source or "\\" in source:
        raise ValueError("Invalid category name")
    sanitized = sanitize_category(source)
    if not sanitized:
        raise ValueError("Invalid category name")
    return sanitized


def resolve_category_dir(download_root: Path, category: str) -> Path:
    candidate = download_root / category if category else download_root
    resolved = candidate.resolve()
    root = download_root.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError("Invalid category path") from exc
    return resolved


def parse_client_ip(req: Any, trust_proxy: bool) -> Optional[ipaddress._BaseAddress]:
    candidate = req.remote_addr
    if trust_proxy:
        header = req.headers.get("X-Forwarded-For", "")
        if header:
            candidate = header.split(",")[0].strip()
    if not candidate:
        return None
    try:
        return ipaddress.ip_address(candidate)
    except ValueError:
        return None


def get_existing_categories(downloads_dir: Path) -> list[str]:
    if not downloads_dir.exists():
        return []
    categories = []
    try:
        for item in downloads_dir.iterdir():
            if item.is_dir() and not item.name.startswith("."):
                categories.append(item.name)
    except OSError:
        return []
    return sorted(categories)
