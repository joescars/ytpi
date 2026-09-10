import os
import queue
import re
import signal
import subprocess
import threading
import time
import uuid
from typing import Any

from .config import AUDIO_ONLY_CATEGORY, Config, get_playlist_id, resolve_category_dir, setup_logging, utc_now, validate_audio_format, validate_quality
from .repository import JobRepository

PROGRESS_RE = re.compile(r"\[download\]\s+(\d+(?:\.\d+)?)%.*?(?:at\s+([^\s]+))?.*?(?:ETA\s+([0-9:]+))?", re.IGNORECASE)
DESTINATION_RE = re.compile(r"\[download\]\s+Destination:\s+(.+)")
PLAYLIST_TITLE_RE = re.compile(
    r"\[(?:youtube:tab|download)\]\s+(?:Downloading|Finished downloading) playlist:\s+(.+)",
    re.IGNORECASE,
)
PROGRESS_FLUSH_INTERVAL_SECONDS = 1.0


def _kill_process_group(proc: "subprocess.Popen[str]") -> None:
    """Kill proc and any children it spawned (e.g. ffmpeg) via its process group."""
    if proc.poll() is not None:
        return
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
    except (ProcessLookupError, PermissionError, OSError):
        proc.kill()


class DownloadManager:
    def __init__(self, config: Config, repo: JobRepository, logger: Any | None = None):
        self.config = config
        self.repo = repo
        self.logger = logger or setup_logging()
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
            # No worker threads (YTPI_MAX_WORKERS=0, e.g. in tests). Only report unhealthy
            # if there's actually work sitting in the queue with nothing to process it.
            return self.download_queue.empty()
        return all(thread.is_alive() for thread in self.workers)

    def shutdown(self) -> None:
        with self.process_lock:
            procs = list(self.running_processes.values())
        for proc in procs:
            _kill_process_group(proc)

    def enqueue(self, url: str, category: str, quality: str, audio_only: bool = False, audio_format: str = "") -> str:
        if self.repo.count_active() >= self.config.max_queue_size:
            raise ValueError("Queue is full. Try again later.")

        self.repo.prune_terminal_jobs(self.config.job_retention_hours, self.config.max_history_jobs)
        job_id = str(uuid.uuid4())
        self.repo.create_job(job_id, url, category, quality, audio_only=audio_only, audio_format=audio_format)
        self.download_queue.put(job_id)
        return job_id

    def cancel_job(self, job_id: str) -> bool:
        job = self.repo.get_job(job_id)
        if not job:
            return False
        if job["status"] in {"finished", "error", "cancelled"}:
            return True

        cancelled = self.repo.update_job_if_status_in(
            job_id, {"queued", "downloading"}, status="cancelled", error="Cancelled by user", finished_at=utc_now()
        )
        if not cancelled:
            # Job reached a terminal state (e.g. finished) between our read and the update.
            return True

        with self.process_lock:
            proc = self.running_processes.get(job_id)
            if proc:
                _kill_process_group(proc)
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
            except Exception as exc:  # pragma: no cover
                self.logger.error("Worker loop failure", extra={"context": {"job_id": job_id, "worker_id": worker_id, "error": str(exc)}})
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
        started = self.repo.update_job_if_status_in(
            job_id,
            {"queued", "downloading"},
            status="downloading",
            output="",
            error="",
            attempt_count=attempt_count,
            started_at=utc_now(),
            progress=0.0,
            eta=None,
            speed=None,
        )
        if not started:
            # Job was cancelled between the read above and this atomic transition.
            return
        job = self.repo.get_job(job_id)
        if not job:
            return

        category_dir = resolve_category_dir(self.config.downloads_dir, job["category"])
        category_dir.mkdir(parents=True, exist_ok=True)

        ffmpeg_args = ["--ffmpeg-location", self.config.ffmpeg_path] if self.config.ffmpeg_path else []
        output_template = "%(playlist)s/%(title)s.%(ext)s" if "playlist?list=" in job["url"] else "%(title)s.%(ext)s"

        remote_component_args = ["--remote-components", "ejs:github"] if self.config.enable_remote_components else []

        audio_only = bool(job.get("audio_only"))
        if audio_only:
            audio_fmt = validate_audio_format(job.get("audio_format") or "")
            cmd = [
                self.config.yt_dlp_binary,
                *remote_component_args,
                *ffmpeg_args,
                "--extract-audio",
                "--audio-format", audio_fmt,
                "-P", str(category_dir),
                "--embed-metadata",
                "-o", output_template,
                job["url"],
            ]
        else:
            quality = validate_quality(job["quality"])
            format_str = "bestvideo+bestaudio/best" if quality == "max" else f"bestvideo[height<={quality}]+bestaudio/best"
            subtitle_flags = ["--write-auto-subs", "--sub-langs", "en", "--convert-subs", "srt"]
            cmd = [
                self.config.yt_dlp_binary,
                *remote_component_args,
                *ffmpeg_args,
                "-f", format_str,
                "-P", str(category_dir),
                "--embed-metadata",
                *subtitle_flags,
                "-o", output_template,
                job["url"],
            ]

        log_context = {"job_id": job_id, "worker_id": worker_id, "attempt": attempt_count, "url": job["url"], "audio_only": audio_only}
        playlist_id = get_playlist_id(job["url"])
        if playlist_id:
            self.repo.upsert_playlist(job["url"], playlist_id, job["category"], job["quality"], audio_only, job.get("audio_format") or "")
        if audio_only:
            log_context["audio_format"] = validate_audio_format(job.get("audio_format") or "")
        else:
            log_context["quality"] = validate_quality(job["quality"])
        self.logger.info("Starting download", extra={"context": log_context})

        timed_out = False
        output_tail = ""

        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1, start_new_session=True
        )

        def on_timeout() -> None:
            nonlocal timed_out
            timed_out = True
            _kill_process_group(proc)

        timeout_timer = threading.Timer(self.config.job_timeout_seconds, on_timeout)
        timeout_timer.start()

        with self.process_lock:
            self.running_processes[job_id] = proc

        current = self.repo.get_job(job_id)
        if current and current["status"] == "cancelled":
            _kill_process_group(proc)

        try:
            if proc.stdout is not None:
                pending_updates: dict[str, Any] = {}
                last_flush = 0.0
                for line in proc.stdout:
                    output_tail = (output_tail + line)[-self.config.max_output_chars :]

                    progress_match = PROGRESS_RE.search(line)
                    if progress_match:
                        progress_str, speed, eta = progress_match.groups()
                        try:
                            pending_updates["progress"] = float(progress_str)
                        except ValueError:
                            pass
                        if speed:
                            pending_updates["speed"] = speed
                        if eta:
                            pending_updates["eta"] = eta

                    destination_match = DESTINATION_RE.search(line)
                    if destination_match:
                        pending_updates["filename"] = destination_match.group(1).strip()

                    playlist_title_match = PLAYLIST_TITLE_RE.search(line)
                    if playlist_title_match:
                        self.repo.update_playlist_name(job["url"], playlist_title_match.group(1).strip())

                    now = time.monotonic()
                    # Persist on a cadence rather than on every line - yt-dlp can emit dozens
                    # of progress lines per second, and each write is a synchronous SQLite
                    # commit. Always flush on a destination change so the filename shows up
                    # promptly.
                    if destination_match or now - last_flush >= PROGRESS_FLUSH_INTERVAL_SECONDS:
                        self.repo.update_job(job_id, output=output_tail, **pending_updates)
                        pending_updates = {}
                        last_flush = now

                if pending_updates or output_tail:
                    self.repo.update_job(job_id, output=output_tail, **pending_updates)

            proc.wait()
        finally:
            timeout_timer.cancel()
            with self.process_lock:
                self.running_processes.pop(job_id, None)

        latest = self.repo.get_job(job_id)
        if latest and latest["status"] == "cancelled":
            return

        final_output = output_tail
        if proc.returncode == 0 and not timed_out:
            self.repo.update_job(job_id, status="finished", output=final_output, progress=100.0, finished_at=utc_now())
            return

        reason = "Timed out" if timed_out else f"yt-dlp exited with code {proc.returncode}"
        error_tail = final_output[-1000:] if final_output else reason

        if attempt_count <= self.config.max_retries:
            self.repo.update_job(job_id, status="queued", output=final_output, error=f"{reason}. Retrying ({attempt_count}/{self.config.max_retries})")
            self.download_queue.put(job_id)
            return

        self.repo.update_job(job_id, status="error", output=final_output, error=error_tail, finished_at=utc_now())
