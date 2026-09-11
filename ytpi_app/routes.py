import atexit
import hmac
import os

from flask import Flask, abort, jsonify, redirect, render_template, request, url_for

from .config import (
    AUDIO_ONLY_CATEGORY,
    get_existing_categories,
    load_config,
    normalize_category_input,
    normalize_urls,
    parse_client_ip,
    parse_int,
    resolve_category_dir,
    setup_logging,
    validate_audio_format,
    validate_quality,
    validate_url,
    get_playlist_id,
)
from .manager import DownloadManager
from .repository import JobRepository


def create_app() -> Flask:
    app = Flask(__name__, template_folder="../templates", static_folder="../static")
    config = load_config()
    logger = setup_logging()

    app.config["MAX_CONTENT_LENGTH"] = config.max_content_length

    config.downloads_dir.mkdir(parents=True, exist_ok=True)
    repo = JobRepository(config.db_path)
    manager = DownloadManager(config, repo, logger)
    atexit.register(manager.shutdown)

    app.config["ytpi_config"] = config
    app.config["ytpi_repo"] = repo
    app.config["ytpi_manager"] = manager

    @app.before_request
    def restrict_to_local() -> None:
        client_ip = parse_client_ip(request, config.trust_proxy)
        if client_ip is None or not any(client_ip in network for network in config.allowed_cidrs):
            logger.warning(
                "Blocked request from disallowed IP",
                extra={"context": {"remote_addr": request.remote_addr, "path": request.path}},
            )
            abort(403)

    def json_or_html_error(message: str, status_code: int, form_data=None):
        if request.is_json:
            return jsonify({"error": message}), status_code
        categories = get_existing_categories(config.downloads_dir)
        
        # If form_data is provided, use it; otherwise get from request.form for HTML responses
        if form_data is None and not request.is_json:
            form_data = request.form
        
        # Extract form values with defaults
        audio_only_val = form_data.get('audio_only', '') if form_data else ''
        # Convert checkbox value to boolean for template
        audio_only_checked = audio_only_val.lower() in {'on', 'true', '1', 'yes'}
        
        form_values = {
            'url': form_data.get('url', '') if form_data else '',
            'category': form_data.get('category', '') if form_data else '',
            'customCategory': form_data.get('customCategory', '') if form_data else '',
            'quality': form_data.get('quality', '') if form_data else '',
            'audio_only': audio_only_checked,
            'audio_format': form_data.get('audio_format', '') if form_data else '',
        }
        
        return render_template(
            "index.html", 
            error=message, 
            categories=categories,
            **form_values
        ), status_code

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
            return json_or_html_error("Invalid category name", 400, data)
        quality = validate_quality((data.get("quality") or "").strip())

        audio_only_raw = data.get("audio_only", "")
        audio_only = str(audio_only_raw).lower() in {"true", "1", "yes", "on"}
        audio_format = validate_audio_format((data.get("audio_format") or "").strip())

        if (data.get("category") or "").strip() == "__custom__":
            category = custom_category or ""
            if not category:
                return json_or_html_error("Custom category name is required", 400, data)

        if audio_only:
            category = AUDIO_ONLY_CATEGORY

        urls = normalize_urls(urls_input)
        if not urls:
            return json_or_html_error("Missing url or urls", 400, data)

        invalid_urls = []
        for url in urls:
            if not validate_url(url, config.block_private_urls):
                invalid_urls.append(url)
        
        if invalid_urls:
            if len(invalid_urls) == 1:
                return json_or_html_error(f"Invalid URL: {invalid_urls[0]}", 400, data)
            else:
                # Show first invalid URL as example
                return json_or_html_error(f"Multiple invalid URLs (e.g., {invalid_urls[0]})", 400, data)

        try:
            resolve_category_dir(config.downloads_dir, category)
        except ValueError:
            return json_or_html_error("Invalid category name", 400, data)

        try:
            job_ids = [manager.enqueue(url, category, quality, audio_only=audio_only, audio_format=audio_format) for url in urls]
        except ValueError as exc:
            message = str(exc)
            return (jsonify({"error": message}), 429) if request.is_json else json_or_html_error(message, 429, data)

        for url in urls:
            playlist_id = get_playlist_id(url)
            if playlist_id:
                repo.upsert_playlist(url, playlist_id, category, quality, audio_only, audio_format)

        if not request.is_json:
            if len(job_ids) == 1:
                return redirect(url_for("status") + f"?job={job_ids[0]}")
            return redirect(url_for("status"))

        return (jsonify({"job_id": job_ids[0]}), 202) if len(job_ids) == 1 else (jsonify({"job_ids": job_ids}), 202)

    @app.route("/share", methods=["GET"])
    def share_via_get():
        if not config.enable_share_get:
            return jsonify({"error": "GET share endpoint is disabled"}), 405

        if not config.share_token:
            # No token configured means there is no way to authenticate this GET request
            # beyond the IP allowlist, and GET requests can be triggered cross-site without
            # user interaction. Refuse rather than silently operate unauthenticated.
            return jsonify({"error": "Share endpoint requires YTPI_SHARE_TOKEN to be configured"}), 403

        token = (request.args.get("token") or "").strip()
        if not hmac.compare_digest(token, config.share_token):
            return jsonify({"error": "Invalid share token"}), 401

        url = (request.args.get("url") or "").strip()
        try:
            category = normalize_category_input(request.args.get("category") or "")
        except ValueError:
            return jsonify({"error": "Invalid category name"}), 400
        quality = validate_quality((request.args.get("quality") or "").strip())
        if not url:
            return jsonify({"error": "Missing url"}), 400
        if not validate_url(url, config.block_private_urls):
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

    @app.route("/api/playlists", methods=["GET"])
    def api_playlists():
        return jsonify({"items": repo.list_playlists()})

    @app.route("/api/playlists/<int:playlist_id>/sync", methods=["POST"])
    def sync_playlist(playlist_id: int):
        playlist = repo.get_playlist(playlist_id)
        if not playlist:
            return jsonify({"error": "Playlist not found"}), 404
        try:
            job_id = manager.enqueue(
                playlist["url"], playlist["category"], playlist["quality"],
                audio_only=bool(playlist["audio_only"]), audio_format=playlist["audio_format"],
            )
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 429
        repo.mark_playlist_synced(playlist_id)
        return jsonify({"job_id": job_id}), 202

    @app.route("/job_output/<job_id>")
    def job_output(job_id: str):
        job = repo.get_job(job_id)
        if not job:
            return jsonify({"error": "Job not found"}), 404
        return jsonify({
            "output": job.get("output", ""),
            "status": job.get("status"),
            "progress": job.get("progress"),
            "eta": job.get("eta"),
            "speed": job.get("speed"),
            "filename": job.get("filename"),
            "error": job.get("error"),
        })

    @app.route("/jobs/<job_id>/cancel", methods=["POST"])
    def cancel_job(job_id: str):
        ok = manager.cancel_job(job_id)
        logger.info(
            "Job cancel requested",
            extra={"context": {"remote_addr": request.remote_addr, "job_id": job_id, "found": ok}},
        )
        if not ok:
            return jsonify({"error": "Job not found"}), 404
        return jsonify({"status": "success", "message": "Job cancelled"})

    @app.route("/jobs/<job_id>/retry", methods=["POST"])
    def retry_job(job_id: str):
        ok = manager.retry_job(job_id)
        logger.info(
            "Job retry requested",
            extra={"context": {"remote_addr": request.remote_addr, "job_id": job_id, "accepted": ok}},
        )
        if not ok:
            return jsonify({"error": "Job cannot be retried"}), 400
        return jsonify({"status": "success", "message": "Job re-queued"})

    @app.route("/clear-finished", methods=["POST"])
    def clear_finished():
        removed = repo.clear_terminal_jobs()
        logger.info(
            "Cleared finished jobs",
            extra={"context": {"remote_addr": request.remote_addr, "removed": removed}},
        )
        return jsonify({"status": "success", "message": f"Cleared {removed} finished job(s)"})

    @app.route("/")
    def home():
        categories = get_existing_categories(config.downloads_dir)
        return render_template("index.html", categories=categories)

    return app
