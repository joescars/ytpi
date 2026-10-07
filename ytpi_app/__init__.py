from __future__ import annotations

import atexit
import hmac
import ipaddress
import os
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from flask import Flask, abort, jsonify, redirect, render_template, request, url_for

from .config import AUDIO_FORMATS, QUALITIES, Settings, client_allowed, load_settings, safe_category, valid_media_url
from .manager import DownloadManager
from .repository import JobRepository


def create_app(settings: Settings | None = None) -> Flask:
    settings = settings or load_settings()
    app = Flask(__name__, template_folder="../templates", static_folder="../static")
    app.config["MAX_CONTENT_LENGTH"] = int(os.getenv("YTPI_MAX_CONTENT_LENGTH", "65536"))
    settings.downloads_dir.mkdir(parents=True, exist_ok=True)
    repo = JobRepository(settings.db_path)
    manager = DownloadManager(settings, repo)
    app.extensions["ytpi_repository"] = repo
    app.extensions["ytpi_manager"] = manager
    app.extensions["ytpi_settings"] = settings
    atexit.register(manager.shutdown)

    @app.before_request
    def restrict_network_access() -> None:
        if not client_allowed(request.remote_addr, request.headers.get("X-Forwarded-For", ""), settings):
            abort(403)

    @app.get("/")
    def home():
        categories = sorted(path.name for path in settings.downloads_dir.iterdir()
                            if path.is_dir() and not path.name.startswith("."))
        items, total = repo.list_jobs(limit=8)
        return render_template("index.html", categories=categories, recent_jobs=items, total_jobs=total)

    @app.get("/status")
    def status_page():
        return redirect(url_for("home") + "#downloads")

    @app.get("/api/jobs")
    def list_jobs():
        limit = _integer_arg("limit", 50, 1, 200)
        offset = _integer_arg("offset", 0, 0, 10_000_000)
        status_filter = request.args.get("status", "").strip()
        if status_filter and status_filter not in {"queued", "downloading", "finished", "error", "cancelled"}:
            return jsonify(error="Invalid status filter."), 400
        items, total = repo.list_jobs(limit=limit, offset=offset, status=status_filter,
                                      search=request.args.get("search", "").strip())
        return jsonify(items=items, total=total, limit=limit, offset=offset, status_counts=repo.status_counts())

    @app.get("/api/status")
    def legacy_status():
        return list_jobs()

    @app.get("/api/playlists")
    def list_playlists():
        return jsonify(items=repo.list_playlists())

    @app.put("/api/playlists/<int:playlist_id>")
    def update_playlist(playlist_id: int):
        playlist = repo.get_playlist(playlist_id)
        if not playlist:
            return jsonify(error="Playlist not found."), 404
        data = request.get_json(silent=True) or {}
        try:
            raw_category = str(data.get("category", playlist["category"]) or "")
            category = safe_category(raw_category) if raw_category else ""
        except ValueError as error:
            return jsonify(error=str(error)), 400
        quality = str(data.get("quality", playlist["quality"]))
        audio_format = str(data.get("audio_format", playlist["audio_format"] or "mp3")).lower()
        if quality not in QUALITIES or audio_format not in AUDIO_FORMATS:
            return jsonify(error="Choose a supported quality and audio format."), 400
        audio_only = str(data.get("audio_only", playlist["audio_only"])).lower() in {"true", "1", "yes", "on"}
        repo.update_playlist_settings(playlist_id, "audio-only" if audio_only else category, quality, audio_only, audio_format)
        return jsonify(playlist=repo.get_playlist(playlist_id))

    @app.post("/api/playlists/<int:playlist_id>/sync")
    def sync_playlist(playlist_id: int):
        playlist = repo.get_playlist(playlist_id)
        if not playlist:
            return jsonify(error="Playlist not found."), 404
        if playlist["sync_status"] in {"requested", "syncing"}:
            return jsonify(error="This playlist is already syncing."), 409
        try:
            job = manager.enqueue(playlist["url"], playlist["category"], playlist["quality"],
                                  bool(playlist["audio_only"]), playlist["audio_format"] or "mp3", playlist_id)
        except ValueError as error:
            return jsonify(error=str(error)), 429
        return jsonify(job=job), 202

    @app.post("/api/jobs")
    def create_job():
        data = request.get_json(silent=True) if request.is_json else request.form
        data = data or {}
        raw_urls = data.get("urls", data.get("url", ""))
        urls = [part.strip() for part in raw_urls if isinstance(part, str) and part.strip()] if isinstance(raw_urls, list) else [part.strip() for part in str(raw_urls).replace(",", "\n").splitlines() if part.strip()]
        if not urls:
            return jsonify(error="Add at least one video or playlist URL."), 400
        invalid = next((url for url in urls if not valid_media_url(url, settings.block_private_urls)), None)
        if invalid:
            return jsonify(error=f"Enter a valid http or https URL: {invalid}"), 400
        quality = str(data.get("quality", "max"))
        if quality not in QUALITIES:
            return jsonify(error="Choose a supported video quality."), 400
        audio_raw = data.get("audio_only", False)
        audio_only = str(audio_raw).lower() in {"true", "1", "yes", "on"}
        audio_format = str(data.get("audio_format", "mp3")).lower()
        if audio_format not in AUDIO_FORMATS:
            return jsonify(error="Choose MP3 or WAV audio."), 400
        try:
            raw_category = str(data.get("custom_category") or data.get("category") or "")
            if raw_category == "__custom__":
                raw_category = ""
            category = "audio-only" if audio_only else (safe_category(raw_category) if raw_category else "")
            if data.get("category") == "__custom__" and not data.get("custom_category"):
                raise ValueError("Enter a name for the new folder.")
            queue_items = []
            for url in urls:
                playlist_id = _playlist_identity(url)
                playlist = repo.upsert_playlist(url, playlist_id, category, quality, audio_only, audio_format) if playlist_id else None
                queue_items.append({"url": url, "category": category, "quality": quality,
                                    "audio_only": audio_only, "audio_format": audio_format,
                                    "playlist_id": playlist["id"] if playlist else None})
            jobs = manager.enqueue_many(queue_items)
        except ValueError as error:
            return jsonify(error=str(error)), 429 if "queue" in str(error).lower() else 400
        if request.is_json:
            return jsonify(jobs=jobs, total=len(jobs)), 202
        return redirect(url_for("home") + "#downloads", code=303)

    @app.post("/download")
    def legacy_create_job():
        return create_job()

    @app.get("/api/jobs/<job_id>")
    @app.get("/job_output/<job_id>")
    def get_job(job_id: str):
        job = repo.get_job(job_id)
        return (jsonify(job), 200) if job else (jsonify(error="Job not found."), 404)

    @app.post("/api/jobs/<job_id>/cancel")
    @app.post("/jobs/<job_id>/cancel")
    def cancel_job(job_id: str):
        return (jsonify(status="cancelled"), 200) if manager.cancel(job_id) else (jsonify(error="Job cannot be cancelled."), 409)

    @app.post("/api/jobs/<job_id>/retry")
    @app.post("/jobs/<job_id>/retry")
    def retry_job(job_id: str):
        return (jsonify(status="queued"), 202) if manager.retry(job_id) else (jsonify(error="Job cannot be retried."), 409)

    @app.delete("/api/jobs/completed")
    @app.post("/clear-finished")
    def clear_finished():
        removed = repo.clear_finished()
        return jsonify(removed=removed, status="success", message=f"Cleared {removed} finished job(s). Downloaded files remain untouched.")

    @app.get("/healthz")
    def healthz():
        db_ok = repo.health_check()
        workers_alive = manager.healthy()
        healthy = db_ok and workers_alive
        return jsonify(status="ok" if healthy else "degraded", database=db_ok, workers=workers_alive,
                       db_ok=db_ok, workers_alive=workers_alive), 200 if healthy else 503

    @app.get("/readyz")
    def readyz():
        downloads_writable = settings.downloads_dir.is_dir() and os.access(settings.downloads_dir, os.W_OK)
        queue_available = repo.count_active() < settings.queue_limit
        db_ok = repo.health_check()
        workers_alive = manager.healthy()
        ready = downloads_writable and queue_available and db_ok and workers_alive
        return jsonify(status="ready" if ready else "not_ready", downloads_writable=downloads_writable,
                       queue_available=queue_available, workers_alive=workers_alive, db_ok=db_ok), 200 if ready else 503

    @app.get("/share")
    def share():
        if os.getenv("YTPI_ENABLE_SHARE_GET", "1").lower() in {"0", "false", "no", "off"}:
            return jsonify(error="Share links are disabled."), 405
        token = os.getenv("YTPI_SHARE_TOKEN", "")
        if not token:
            return jsonify(error="Set YTPI_SHARE_TOKEN before using the share link."), 403
        if not hmac.compare_digest(request.args.get("token", ""), token):
            return jsonify(error="A valid share token is required."), 401
        url = request.args.get("url", "")
        if not valid_media_url(url, settings.block_private_urls):
            return jsonify(error="Enter a valid http or https URL."), 400
        try:
            category = safe_category(request.args.get("category", "Shared"))
            job = manager.enqueue(url, category, request.args.get("quality", "max"))
        except ValueError as error:
            return jsonify(error=str(error)), 400
        if request.args.get("redirect", "1").lower() in {"0", "false", "no"}:
            return render_template("shared_success.html", job=job), 202
        return redirect(url_for("home") + "#downloads", code=303)

    @app.get("/robots.txt")
    def robots_txt():
        return "User-agent: *\nDisallow: /\n", 200, {"Content-Type": "text/plain; charset=utf-8"}

    return app


def _playlist_identity(url: str) -> str:
    parsed = urlparse(url)
    if (parsed.hostname or "").lower() not in {"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com"}:
        return ""
    values = parse_qs(parsed.query)
    playlist_id = values.get("list", [""])[0].strip()
    path = parsed.path.rstrip("/")
    if not playlist_id or (path == "/watch" and values.get("v", [""])[0]):
        return ""
    return playlist_id if path in {"/playlist", "/watch"} else ""


def _integer_arg(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        return max(minimum, min(maximum, int(request.args.get(name, default))))
    except (TypeError, ValueError):
        return default


def create_app_for_test(settings: Settings) -> Flask:
    return create_app(settings)
