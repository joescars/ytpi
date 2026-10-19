from __future__ import annotations

import os
import queue
import re
import signal
import subprocess
import tempfile
import threading
import uuid
from pathlib import Path
from typing import Any

from .config import Settings, safe_category
from .repository import JobRepository, now_iso

_PROGRESS = re.compile(r"(?P<percent>\d+(?:\.\d+)?)%.*?\bat\s+(?P<speed>[^\s]+).*?\bETA\s+(?P<eta>[0-9:]+)", re.I)
_DESTINATION = re.compile(r"Destination:\s+(.+)$")
_TITLE = re.compile(r"__YTPI_TITLE__(.+)$")
_FILEPATH = re.compile(r"__YTPI_FILEPATH__(.+)$")
_MERGED_FILE = re.compile(r"Merging formats into [\"'](.+)[\"']")


class DownloadManager:
    def __init__(self, settings: Settings, repo: JobRepository):
        self.settings = settings
        self.repo = repo
        self._queue: queue.Queue[str] = queue.Queue()
        self._lock = threading.RLock()
        self._processes: dict[str, subprocess.Popen[str]] = {}
        self._workers: list[threading.Thread] = []
        for job_id in repo.recover_interrupted_jobs():
            self._queue.put(job_id)
        for index in range(settings.workers):
            thread = threading.Thread(target=self._worker, name=f"ytpi-worker-{index + 1}", daemon=True)
            thread.start()
            self._workers.append(thread)

    def enqueue(self, url: str, category: str, quality: str, audio_only: bool = False, audio_format: str = "mp3", playlist_id: int | None = None) -> dict[str, Any]:
        return self.enqueue_many([{"url": url, "category": category, "quality": quality,
                                   "audio_only": audio_only, "audio_format": audio_format,
                                   "playlist_id": playlist_id}])[0]

    def enqueue_many(self, requests: list[dict[str, Any]]) -> list[dict[str, Any]]:
        with self._lock:
            self.repo.prune_terminal_jobs(self.settings.job_retention_hours, self.settings.max_history_jobs)
            if self.repo.count_active() + len(requests) > self.settings.queue_limit:
                raise ValueError("The download queue is full. Try again later.")
            jobs = []
            for item in requests:
                job_id = str(uuid.uuid4())
                job = self.repo.create_job(job_id=job_id, url=item["url"], category=item["category"],
                                           quality=item["quality"], audio_only=item["audio_only"],
                                           audio_format=item["audio_format"], playlist_id=item.get("playlist_id"))
                jobs.append(job)
            for job in jobs:
                if job.get("playlist_id") is not None:
                    self.repo.set_playlist_sync(job["playlist_id"], "requested", job["id"])
                self._queue.put(job["id"])
            return jobs

    def cancel(self, job_id: str) -> bool:
        job = self.repo.get_job(job_id)
        if not job or job["status"] not in {"queued", "downloading"}:
            return False
        self.repo.update_job(job_id, status="cancelled", stage="Cancelled", error="Cancelled by user", finished_at=now_iso())
        with self._lock:
            process = self._processes.get(job_id)
            if process and process.poll() is None:
                try:
                    os.killpg(os.getpgid(process.pid), signal.SIGTERM)
                except (ProcessLookupError, OSError):
                    process.terminate()
        playlist = self.repo.playlist_for_job(job_id)
        if playlist:
            self.repo.set_playlist_sync(playlist["id"], "failed")
        return True

    def retry(self, job_id: str) -> bool:
        job = self.repo.get_job(job_id)
        if not job or job["status"] not in {"error", "cancelled"}:
            return False
        self.repo.update_job(job_id, status="queued", stage="Queued", progress=0, error="", output="",
                             finished_at=None, speed="", eta="")
        self._queue.put(job_id)
        playlist = self.repo.playlist_for_job(job_id)
        if playlist:
            self.repo.set_playlist_sync(playlist["id"], "requested", job_id)
        return True

    def healthy(self) -> bool:
        return all(thread.is_alive() for thread in self._workers)

    def shutdown(self) -> None:
        with self._lock:
            processes = list(self._processes.values())
        for process in processes:
            if process.poll() is None:
                try:
                    os.killpg(os.getpgid(process.pid), signal.SIGTERM)
                except (ProcessLookupError, OSError):
                    process.terminate()

    def _output_tail(self, lines: list[str]) -> str:
        return "\n".join(lines)[-self.settings.max_output_chars:]

    def _embed_thumbnail(self, media_path: Path) -> str | None:
        media_path = media_path.resolve()
        if not media_path.is_relative_to(self.settings.downloads_dir.resolve()) or not media_path.is_file():
            return None
        thumbnail_path = media_path.with_name(f"{media_path.stem}-thumb.jpg")
        if not thumbnail_path.is_file():
            return None

        extension = media_path.suffix.lower()
        if extension not in {".mp3", ".mp4", ".m4a", ".m4v", ".mov", ".mkv", ".mka"}:
            return None

        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(dir=media_path.parent, suffix=extension, delete=False) as temporary:
                temporary_path = Path(temporary.name)
            temporary_path.unlink()
            command = [self.settings.ffmpeg_path or "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                       "-i", str(media_path)]
            if extension not in {".mkv", ".mka"}:
                command += ["-i", str(thumbnail_path)]
            command += ["-map", "0"]
            if extension not in {".mkv", ".mka"}:
                command += ["-map", "1:v:0"]
            command += ["-map_metadata", "0", "-map_chapters", "0", "-c", "copy"]
            if extension in {".mp4", ".m4a", ".m4v", ".mov"}:
                video_index = "0" if extension == ".m4a" else "1"
                command += [f"-disposition:v:{video_index}", "attached_pic"]
            elif extension in {".mkv", ".mka"}:
                command += ["-attach", str(thumbnail_path), "-metadata:s:t", "mimetype=image/jpeg",
                            "-metadata:s:t", "filename=cover.jpg"]
            else:
                command += ["-id3v2_version", "3", "-metadata:s:v", "title=Album cover",
                            "-metadata:s:v", "comment=Cover (front)"]
            command.append(str(temporary_path))
            result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    text=True, timeout=self.settings.timeout_seconds, check=False)
            if result.returncode != 0 or not temporary_path.is_file():
                return f"Thumbnail sidecar saved; embedding failed for {media_path.name}."
            os.replace(temporary_path, media_path)
            return f"Embedded thumbnail in {media_path.name}; kept {thumbnail_path.name}."
        except (OSError, subprocess.TimeoutExpired):
            return f"Thumbnail sidecar saved; embedding failed for {media_path.name}."
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)

    def _worker(self) -> None:
        while True:
            job_id = self._queue.get()
            try:
                job = self.repo.get_job(job_id)
                if job and job["status"] == "queued":
                    self._run(job)
            except Exception as error:
                current = self.repo.get_job(job_id)
                if current and current["status"] in {"queued", "downloading"}:
                    self.repo.update_job(job_id, status="error", stage="Failed", error=f"Unexpected worker error: {error}", finished_at=now_iso())
                    playlist = self.repo.playlist_for_job(job_id)
                    if playlist:
                        self.repo.set_playlist_sync(playlist["id"], "failed", job_id)
            finally:
                self._queue.task_done()

    def _run(self, job: dict[str, Any]) -> None:
        job_id = job["id"]
        category = safe_category(job["category"]) if job["category"] else ""
        destination = (self.settings.downloads_dir / category).resolve()
        destination.mkdir(parents=True, exist_ok=True)
        if not destination.is_relative_to(self.settings.downloads_dir.resolve()):
            self.repo.update_job(job_id, status="error", error="Invalid destination category", stage="Failed", finished_at=now_iso())
            return
        remote = ["--remote-components", "ejs:github"] if self.settings.enable_remote_components else []
        ffmpeg = ["--ffmpeg-location", self.settings.ffmpeg_path] if self.settings.ffmpeg_path else []
        thumbnail_template = str(destination / ("%(playlist)s/%(title)s-thumb.%(ext)s" if "list=" in job["url"]
                                                  else "%(title)s-thumb.%(ext)s"))
        command = [self.settings.yt_dlp, "--newline", "--no-colors", "--progress", "--write-thumbnail",
                   "--convert-thumbnails", "jpg", *remote, *ffmpeg,
                   "--output", f"thumbnail:{thumbnail_template}",
                   "--print", "after_move:__YTPI_TITLE__%(title)s",
                   "--print", "after_move:__YTPI_FILEPATH__%(filepath)s", "-P", str(destination)]
        if job["audio_only"]:
            command += ["--extract-audio", "--audio-format", job["audio_format"] or "mp3"]
        else:
            selector = "bestvideo+bestaudio/best" if job["quality"] == "max" else f"bestvideo[height<={job['quality']}]+bestaudio/best"
            command += ["-f", selector]
            if self.settings.write_auto_subs:
                command += ["--write-auto-subs", "--sub-langs", "en", "--convert-subs", "srt"]
        command += ["-o", "%(playlist)s/%(title)s.%(ext)s" if "list=" in job["url"] else "%(title)s.%(ext)s", job["url"]]
        attempt_count = int(job.get("attempt_count") or 0) + 1
        self.repo.update_job(job_id, status="downloading", stage="Preparing", error="", started_at=now_iso(), attempt_count=attempt_count)
        playlist = self.repo.playlist_for_job(job_id)
        if playlist:
            self.repo.set_playlist_sync(playlist["id"], "syncing", job_id)
        output: list[str] = []
        process: subprocess.Popen[str] | None = None
        try:
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                       bufsize=1, start_new_session=True)
            with self._lock:
                self._processes[job_id] = process
            for line in process.stdout or []:
                clean = line.rstrip()
                output.append(clean)
                output = output[-250:]
                fields: dict[str, Any] = {"output": self._output_tail(output)}
                title = _TITLE.search(clean)
                if title:
                    fields["title"] = title.group(1).strip()
                    if self.repo.playlist_for_job(job_id):
                        self.repo.update_playlist_name(job["url"], title.group(1).strip())
                filepath = _FILEPATH.search(clean)
                if filepath:
                    fields["filename"] = filepath.group(1).strip()
                match = _PROGRESS.search(clean)
                if match and "[download]" in clean:
                    try:
                        fields["progress"] = float(match.group("percent"))
                    except ValueError:
                        pass
                    fields["speed"] = match.group("speed")
                    fields["eta"] = match.group("eta")
                    fields["stage"] = "Downloading"
                if "Destination:" in clean or "Merger" in clean:
                    fields["stage"] = "Processing"
                found = _DESTINATION.search(clean)
                if found:
                    fields["filename"] = found.group(1).strip()
                merged = _MERGED_FILE.search(clean)
                if merged:
                    fields["filename"] = merged.group(1).strip()
                self.repo.update_job(job_id, **fields)
            try:
                returncode = process.wait(timeout=self.settings.timeout_seconds)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                except (ProcessLookupError, OSError):
                    process.kill()
                returncode = process.wait()
                output.append("Download timed out.")
            latest = self.repo.get_job(job_id)
            if latest and latest["status"] == "cancelled":
                return
            if returncode == 0:
                thumbnail_message = None
                latest = self.repo.get_job(job_id)
                filename = latest.get("filename", "") if latest else ""
                if filename:
                    thumbnail_message = self._embed_thumbnail(Path(filename))
                if thumbnail_message:
                    output.append(thumbnail_message)
                self.repo.update_job(job_id, status="finished", stage="Finished", progress=100,
                                     output=self._output_tail(output), finished_at=now_iso())
                playlist = self.repo.playlist_for_job(job_id)
                if playlist:
                    self.repo.set_playlist_sync(playlist["id"], "successful", job_id, success=True)
            elif attempt_count <= self.settings.max_retries:
                message = f"yt-dlp exited with code {returncode}. Retrying ({attempt_count}/{self.settings.max_retries})…"
                self.repo.update_job(job_id, status="queued", stage="Retry scheduled", error=message,
                                     output=self._output_tail(output), finished_at=None)
                playlist = self.repo.playlist_for_job(job_id)
                if playlist:
                    self.repo.set_playlist_sync(playlist["id"], "requested", job_id)
                self._queue.put(job_id)
            else:
                self.repo.update_job(job_id, status="error", stage="Failed", error="\n".join(output[-8:]) or f"yt-dlp exited with {returncode}",
                                     output=self._output_tail(output), finished_at=now_iso())
                playlist = self.repo.playlist_for_job(job_id)
                if playlist:
                    self.repo.set_playlist_sync(playlist["id"], "failed", job_id)
        except OSError as error:
            self.repo.update_job(job_id, status="error", stage="Failed", error=f"Unable to start yt-dlp: {error}", finished_at=now_iso())
            playlist = self.repo.playlist_for_job(job_id)
            if playlist:
                self.repo.set_playlist_sync(playlist["id"], "failed", job_id)
        finally:
            with self._lock:
                self._processes.pop(job_id, None)
