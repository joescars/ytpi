import ipaddress
import json
import logging
import os
import queue
import re
import sqlite3
import subprocess
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse

from flask import Flask, abort, jsonify, redirect, render_template, request, url_for

ALLOWED_QUALITIES = {"max", "2160", "1440", "1080", "720", "480"}
PROGRESS_RE = re.compile(r"\[download\]\s+(\d+(?:\.\d+)?)%.*?(?:at\s+([^\s]+))?.*?(?:ETA\s+([0-9:]+))?", re.IGNORECASE)
DESTINATION_RE = re.compile(r"\[download\]\s+Destination:\s+(.+)")
DEFAULT_ALLOWED_CIDRS = "127.0.0.0/8,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16,::1/128"


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


def parse_bool(value: str, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def parse_int(value: str, default: int, min_value: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(parsed, min_value)


def parse_cidrs(value: str) -> list[ipaddress._BaseNetwork]:
    cidrs: list[ipaddress._BaseNetwork] = []
    for entry in (value or DEFAULT_ALLOWED_CIDRS).split(","):
        item = entry.strip()
        if not item:
            continue
        cidrs.append(ipaddress.ip_network(item, strict=False))
    return cidrs


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


def normalize_urls(urls_input: Any) -> list[str]:
    if isinstance(urls_input, str):
        # Support textarea input by splitting on newlines/commas.
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


class JobRepository:
    def __init__(self, db_path: Path):
        self._lock = threading.RLock()
        self._db_path = db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=NORMAL")
        self._init_schema()

    def _init_schema(self) -> None:
        with self._lock:
            self.conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    url TEXT NOT NULL,
                    status TEXT NOT NULL,
                    category TEXT NOT NULL DEFAULT '',
                    quality TEXT NOT NULL DEFAULT 'max',
                    output TEXT NOT NULL DEFAULT '',
                    error TEXT,
                    progress REAL,
                    eta TEXT,
                    speed TEXT,
                    filename TEXT,
                    attempt_count INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    started_at TEXT,
                    finished_at TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
                CREATE INDEX IF NOT EXISTS idx_jobs_created_at ON jobs(created_at);
                """
            )
            self.conn.commit()

    def reset_stale_downloading_jobs(self) -> None:
        with self._lock:
            now = utc_now()
            self.conn.execute(
                """
                UPDATE jobs
                SET status='queued', updated_at=?, error=COALESCE(error,'')
                WHERE status='downloading'
                """,
                (now,),
            )
            self.conn.commit()

    def create_job(self, job_id: str, url: str, category: str, quality: str) -> None:
        with self._lock:
            now = utc_now()
            self.conn.execute(
                """
                INSERT INTO jobs (id, url, status, category, quality, created_at, updated_at)
                VALUES (?, ?, 'queued', ?, ?, ?, ?)
                """,
                (job_id, url, category, quality, now, now),
            )
            self.conn.commit()

    def get_job(self, job_id: str) -> Optional[dict[str, Any]]:
        with self._lock:
            row = self.conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        return dict(row) if row else None

    def update_job(self, job_id: str, **fields: Any) -> None:
        if not fields:
            return
        fields["updated_at"] = utc_now()
        columns = ", ".join(f"{k} = ?" for k in fields)
        values = list(fields.values()) + [job_id]
        with self._lock:
            self.conn.execute(f"UPDATE jobs SET {columns} WHERE id = ?", values)
            self.conn.commit()

    def list_jobs(self, *, limit: int, offset: int, status: str = "") -> tuple[list[dict[str, Any]], int]:
        safe_limit = max(1, min(limit, 500))
        safe_offset = max(0, offset)
        where = ""
        params: list[Any] = []
        if status:
            where = "WHERE status = ?"
            params.append(status)

        with self._lock:
            total = self.conn.execute(f"SELECT COUNT(*) AS c FROM jobs {where}", params).fetchone()["c"]
            rows = self.conn.execute(
                f"""
                SELECT * FROM jobs
                {where}
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
                """,
                params + [safe_limit, safe_offset],
            ).fetchall()
        return [dict(row) for row in rows], int(total)

    def list_pending_ids(self) -> list[str]:
        with self._lock:
            rows = self.conn.execute(
                "SELECT id FROM jobs WHERE status = 'queued' ORDER BY created_at ASC"
            ).fetchall()
        return [row["id"] for row in rows]

    def count_active(self) -> int:
        with self._lock:
            row = self.conn.execute(
                "SELECT COUNT(*) AS c FROM jobs WHERE status IN ('queued', 'downloading')"
            ).fetchone()
        return int(row["c"])

    def health_check(self) -> bool:
        try:
            with self._lock:
                self.conn.execute("SELECT 1")
            return True
        except sqlite3.Error:
            return False

    def prune_terminal_jobs(self, retention_hours: int, max_history_jobs: int) -> int:
        removed = 0
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=retention_hours)).isoformat()
        with self._lock:
            cur = self.conn.execute(
                """
                DELETE FROM jobs
                WHERE status IN ('finished','error','cancelled')
                  AND updated_at < ?
                """,
                (cutoff,),
            )
            removed += cur.rowcount

            row = self.conn.execute("SELECT COUNT(*) AS c FROM jobs").fetchone()
            total = int(row["c"])
            overflow = total - max_history_jobs
            if overflow > 0:
                cur = self.conn.execute(
                    """
                    DELETE FROM jobs
                    WHERE id IN (
                        SELECT id FROM jobs
                        WHERE status IN ('finished','error','cancelled')
                        ORDER BY updated_at ASC
                        LIMIT ?
                    )
                    """,
                    (overflow,),
                )
                removed += cur.rowcount
            self.conn.commit()
        return removed

    def clear_terminal_jobs(self) -> int:
        with self._lock:
            cur = self.conn.execute(
                "DELETE FROM jobs WHERE status IN ('finished','error','cancelled')"
            )
            removed = cur.rowcount
            self.conn.commit()
        return removed


class DownloadManager:
    def __init__(self, config: Config, repo: JobRepository, logger: logging.Logger):
        self.config = config
        self.repo = repo
        self.logger = logger
        self.download_queue: queue.Queue[str] = queue.Queue()
        self.workers: list[threading.Thread] = []
        self.running_processes: dict[str, subprocess.Popen[str]] = {}
        self.process_lock = threading.RLock()

        self.repo.reset_stale_downloading_jobs()
        for job_id in self.repo.list_pending_ids():
            self.download_queue.put(job_id)

        for worker_id in range(self.config.max_workers):
            thread = threading.Thread(target=self.worker_loop, args=(worker_id,), daemon=True)
            thread.start()
            self.workers.append(thread)

    def is_alive(self) -> bool:
        if not self.workers:
            return True
        return all(thread.is_alive() for thread in self.workers)

    def enqueue(self, url: str, category: str, quality: str) -> str:
        if self.repo.count_active() >= self.config.max_queue_size:
            raise ValueError("Queue is full. Try again later.")

        self.repo.prune_terminal_jobs(self.config.job_retention_hours, self.config.max_history_jobs)
        job_id = str(uuid.uuid4())
        self.repo.create_job(job_id, url, category, quality)
        self.download_queue.put(job_id)
        return job_id

    def cancel_job(self, job_id: str) -> bool:
        job = self.repo.get_job(job_id)
        if not job:
            return False
        if job["status"] in {"finished", "error", "cancelled"}:
            return True

        with self.process_lock:
            proc = self.running_processes.get(job_id)
            if proc and proc.poll() is None:
                proc.kill()

        self.repo.update_job(job_id, status="cancelled", error="Cancelled by user", finished_at=utc_now())
        return True

    def retry_job(self, job_id: str) -> bool:
        job = self.repo.get_job(job_id)
        if not job:
            return False
        if job["status"] not in {"error", "cancelled"}:
            return False

        self.repo.update_job(
            job_id,
            status="queued",
            error="",
            output="",
            progress=None,
            eta=None,
            speed=None,
            filename=None,
            finished_at=None,
        )
        self.download_queue.put(job_id)
        return True

    def worker_loop(self, worker_id: int) -> None:
        while True:
            job_id = self.download_queue.get()
            try:
                self._process_job(job_id, worker_id)
            except Exception as exc:  # pragma: no cover - guardrail for worker loop
                self.logger.error(
                    "Worker loop failure",
                    extra={"context": {"job_id": job_id, "worker_id": worker_id, "error": str(exc)}},
                )
                self.repo.update_job(job_id, status="error", error=f"Unexpected worker error: {exc}", finished_at=utc_now())
            finally:
                self.download_queue.task_done()

    def _process_job(self, job_id: str, worker_id: int) -> None:
        job = self.repo.get_job(job_id)
        if not job:
            return
        if job["status"] not in {"queued", "downloading"}:
            return

        attempt_count = int(job["attempt_count"] or 0) + 1
        self.repo.update_job(
            job_id,
            status="downloading",
            output="",
            error="",
            attempt_count=attempt_count,
            started_at=utc_now(),
            progress=0.0,
            eta=None,
            speed=None,
        )

        category_dir = resolve_category_dir(self.config.downloads_dir, job["category"])
        category_dir.mkdir(parents=True, exist_ok=True)

        quality = validate_quality(job["quality"])
        format_str = "bestvideo+bestaudio/best" if quality == "max" else f"bestvideo[height<={quality}]+bestaudio/best"
        subtitle_flags = ["--write-auto-subs", "--sub-langs", "en", "--convert-subs", "srt"]
        ffmpeg_args = ["--ffmpeg-location", self.config.ffmpeg_path] if self.config.ffmpeg_path else []
        output_template = "%(playlist)s/%(title)s.%(ext)s" if "playlist?list=" in job["url"] else "%(title)s.%(ext)s"

        cmd = [
            self.config.yt_dlp_binary,
            *ffmpeg_args,
            "-f",
            format_str,
            "-P",
            str(category_dir),
            "--embed-metadata",
            *subtitle_flags,
            "-o",
            output_template,
            job["url"],
        ]

        self.logger.info(
            "Starting download",
            extra={
                "context": {
                    "job_id": job_id,
                    "worker_id": worker_id,
                    "attempt": attempt_count,
                    "url": job["url"],
                    "quality": quality,
                }
            },
        )

        timed_out = False
        output_buffer: list[str] = []

        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )

        def on_timeout() -> None:
            nonlocal timed_out
            timed_out = True
            if proc.poll() is None:
                proc.kill()

        timeout_timer = threading.Timer(self.config.job_timeout_seconds, on_timeout)
        timeout_timer.start()

        with self.process_lock:
            self.running_processes[job_id] = proc

        try:
            if proc.stdout is not None:
                for line in proc.stdout:
                    output_buffer.append(line)
                    latest_output = "".join(output_buffer)[-self.config.max_output_chars :]
                    updates: dict[str, Any] = {"output": latest_output}

                    progress_match = PROGRESS_RE.search(line)
                    if progress_match:
                        progress_str, speed, eta = progress_match.groups()
                        try:
                            updates["progress"] = float(progress_str)
                        except ValueError:
                            pass
                        if speed:
                            updates["speed"] = speed
                        if eta:
                            updates["eta"] = eta

                    destination_match = DESTINATION_RE.search(line)
                    if destination_match:
                        updates["filename"] = destination_match.group(1).strip()

                    self.repo.update_job(job_id, **updates)

            proc.wait()
        finally:
            timeout_timer.cancel()
            with self.process_lock:
                self.running_processes.pop(job_id, None)

        latest = self.repo.get_job(job_id)
        if latest and latest["status"] == "cancelled":
            return

        final_output = "".join(output_buffer)[-self.config.max_output_chars :]
        if proc.returncode == 0 and not timed_out:
            self.repo.update_job(
                job_id,
                status="finished",
                output=final_output,
                progress=100.0,
                finished_at=utc_now(),
            )
            return

        reason = "Timed out" if timed_out else f"yt-dlp exited with code {proc.returncode}"
        error_tail = final_output[-1000:] if final_output else reason

        if attempt_count <= self.config.max_retries:
            self.repo.update_job(
                job_id,
                status="queued",
                output=final_output,
                error=f"{reason}. Retrying ({attempt_count}/{self.config.max_retries})",
            )
            self.download_queue.put(job_id)
            return

        self.repo.update_job(
            job_id,
            status="error",
            output=final_output,
            error=error_tail,
            finished_at=utc_now(),
        )


def create_app() -> Flask:
    app = Flask(__name__)
    config = load_config()
    logger = setup_logging()

    config.downloads_dir.mkdir(parents=True, exist_ok=True)
    repo = JobRepository(config.db_path)
    manager = DownloadManager(config, repo, logger)

    app.config["ytpi_config"] = config
    app.config["ytpi_repo"] = repo
    app.config["ytpi_manager"] = manager

    @app.before_request
    def restrict_to_local() -> None:
        client_ip = parse_client_ip(request, config.trust_proxy)
        if client_ip is None:
            abort(403)
        if not any(client_ip in network for network in config.allowed_cidrs):
            abort(403)

    def json_or_html_error(message: str, status_code: int):
        if request.is_json:
            return jsonify({"error": message}), status_code
        categories = get_existing_categories(config.downloads_dir)
        return render_template("index.html", error=message, categories=categories), status_code

    @app.route("/healthz", methods=["GET"])
    def healthz():
        payload = {
            "status": "ok" if repo.health_check() and manager.is_alive() else "degraded",
            "workers_alive": manager.is_alive(),
            "db_ok": repo.health_check(),
        }
        return jsonify(payload), (200 if payload["status"] == "ok" else 503)

    @app.route("/readyz", methods=["GET"])
    def readyz():
        writable = os.access(str(config.downloads_dir), os.W_OK)
        queue_available = repo.count_active() < config.max_queue_size
        ready = writable and queue_available and repo.health_check() and manager.is_alive()
        payload = {
            "status": "ready" if ready else "not_ready",
            "downloads_writable": writable,
            "queue_available": queue_available,
            "workers_alive": manager.is_alive(),
            "db_ok": repo.health_check(),
        }
        return jsonify(payload), (200 if ready else 503)

    @app.route("/download", methods=["POST"])
    def enqueue_download():
        data = request.get_json(force=True) if request.is_json else request.form
        urls_input = data.get("url") or data.get("urls")
        try:
            category = normalize_category_input(data.get("category", ""))
            custom_category = normalize_category_input(data.get("customCategory", ""))
        except ValueError:
            return json_or_html_error("Invalid category name", 400)
        quality = validate_quality((data.get("quality") or "").strip())

        if (data.get("category") or "").strip() == "__custom__":
            if custom_category:
                category = custom_category
            else:
                return json_or_html_error("Custom category name is required", 400)

        urls = normalize_urls(urls_input)
        if not urls:
            return json_or_html_error("Missing url or urls", 400)

        invalid_urls = [url for url in urls if not validate_url(url)]
        if invalid_urls:
            return json_or_html_error("One or more URLs are invalid", 400)

        try:
            resolve_category_dir(config.downloads_dir, category)
        except ValueError:
            return json_or_html_error("Invalid category name", 400)

        try:
            job_ids = [manager.enqueue(url, category, quality) for url in urls]
        except ValueError as exc:
            message = str(exc)
            if request.is_json:
                return jsonify({"error": message}), 429
            return json_or_html_error(message, 429)

        if not request.is_json:
            if len(job_ids) == 1:
                return redirect(url_for("status") + f"?job={job_ids[0]}")
            return redirect(url_for("status"))

        if len(job_ids) == 1:
            return jsonify({"job_id": job_ids[0]}), 202
        return jsonify({"job_ids": job_ids}), 202

    @app.route("/share", methods=["GET"])
    def share_via_get():
        if not config.enable_share_get:
            return jsonify({"error": "GET share endpoint is disabled"}), 405

        if config.share_token:
            token = (request.args.get("token") or "").strip()
            if token != config.share_token:
                return jsonify({"error": "Invalid share token"}), 401

        url = (request.args.get("url") or "").strip()
        try:
            category = normalize_category_input(request.args.get("category") or "")
        except ValueError:
            return jsonify({"error": "Invalid category name"}), 400
        quality = validate_quality((request.args.get("quality") or "").strip())
        if not url:
            return jsonify({"error": "Missing url"}), 400
        if not validate_url(url):
            return jsonify({"error": "Invalid URL"}), 400

        try:
            job_id = manager.enqueue(url, category, quality)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 429

        redirect_pref = (request.args.get("redirect") or "1").lower()
        if redirect_pref in ("1", "true", "yes"):
            return redirect(url_for("status") + f"?job={job_id}")
        return render_template("shared_success.html", job_id=job_id), 202

    @app.route("/status", methods=["GET"])
    def status():
        jobs, _ = repo.list_jobs(limit=200, offset=0)
        default_job_id = request.args.get("job") or (jobs[0]["id"] if jobs else None)
        return render_template("dashboard.html", jobs=jobs, default_job_id=default_job_id)

    @app.route("/api/status", methods=["GET"])
    def api_status():
        limit = parse_int(request.args.get("limit", "200"), 200, 1)
        offset = parse_int(request.args.get("offset", "0"), 0, 0)
        status_filter = (request.args.get("status") or "").strip()
        jobs, total = repo.list_jobs(limit=limit, offset=offset, status=status_filter)
        return jsonify({"items": jobs, "total": total, "limit": limit, "offset": offset})

    @app.route("/job_output/<job_id>")
    def job_output(job_id: str):
        job = repo.get_job(job_id)
        if not job:
            return jsonify({"error": "Job not found"}), 404
        return jsonify(
            {
                "output": job.get("output", ""),
                "status": job.get("status"),
                "progress": job.get("progress"),
                "eta": job.get("eta"),
                "speed": job.get("speed"),
                "filename": job.get("filename"),
                "error": job.get("error"),
            }
        )

    @app.route("/jobs/<job_id>/cancel", methods=["POST"])
    def cancel_job(job_id: str):
        ok = manager.cancel_job(job_id)
        if not ok:
            return jsonify({"error": "Job not found"}), 404
        return jsonify({"status": "success", "message": "Job cancelled"})

    @app.route("/jobs/<job_id>/retry", methods=["POST"])
    def retry_job(job_id: str):
        ok = manager.retry_job(job_id)
        if not ok:
            return jsonify({"error": "Job cannot be retried"}), 400
        return jsonify({"status": "success", "message": "Job re-queued"})

    @app.route("/clear-finished", methods=["POST"])
    def clear_finished():
        removed = repo.clear_terminal_jobs()
        return jsonify({"status": "success", "message": f"Cleared {removed} finished job(s)"})

    @app.route("/")
    def home():
        categories = get_existing_categories(config.downloads_dir)
        return render_template("index.html", categories=categories)

    return app


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


app = create_app()


if __name__ == "__main__":
    cfg: Config = app.config["ytpi_config"]
    app.run(host=cfg.host, port=cfg.port)
