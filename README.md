# YTPI v2

YTPI is a private, responsive YouTube download manager for your home network. The current root application is the v2 rebuild, using Flask, SQLite, yt-dlp, ffmpeg, and a Material 3–inspired responsive web interface. Earlier v1 source remains available in Git history.

## Current functionality

- Queue one or several HTTP(S) video or playlist links.
- Download video in best available, 4K, 2K, 1080p, 720p, or 480p quality, or extract MP3/WAV audio.
- Monitor download progress, stage, speed, errors, and technical output; search and filter history; load more results.
- Cancel queued or active work and retry failed/cancelled jobs.
- Persist job history and saved playlist settings in SQLite; recover interrupted downloads after restart.
- Edit saved playlist settings and request playlist syncs; show requested, active, failed, and last successful sync state.
- Maintain the CIDR allowlist on every web/API/health endpoint. Optional trusted-proxy handling and literal private-IP blocking are configurable.
- Run in Docker with health checks, persistent database/media mounts, ffmpeg, and the JavaScript runtime used by yt-dlp remote components.

## Local development

```bash
cp .env.example .env
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python app.py
```

Open <http://localhost:7434>. For development, set `YTPI_MAX_WORKERS=0` to prevent queued jobs from starting. Settings come from environment variables; see `.env.example`. Do not expose the service directly to the public internet. The CIDR allowlist is network access control, not user authentication.

Run tests:

```bash
.venv/bin/python -m pytest -q
```

## Docker deployment

The root Compose app pulls the public `ghcr.io/joescars/ytpi` image, retains the established container/service name `ytpi`, publishes port **7434**, mounts job history from `./data`, and uses `/mnt/usb0/samsung/media/YouTube` for media by default. It uses the `latest` image tag unless `YTPI_IMAGE_TAG` is set. Override `YTPI_HOST_DOWNLOADS_DIR` if the deployment host uses a different media path.

```bash
docker compose config --quiet
docker compose pull ytpi
docker compose up -d --no-build
docker compose ps
curl --fail http://localhost:7434/healthz
curl --fail http://localhost:7434/readyz
```

The deployment workflow is manually dispatched. It updates only the Compose file on the host, pulls the published image, and creates a consistent SQLite backup under `.deployment-backups/` before restarting the service. V2 applies additive schema migration to the existing `data/jobs.db`; keep the backup until the new site and history are verified. The host `.env`, database, and existing mounted media directory are preserved. Do not run two app versions against the same SQLite database concurrently.

To stop the service without deleting bind-mounted history or media, run `docker compose down` from the deployment directory. Do not run `docker compose down -v` if you want to preserve Compose-managed volumes.

The v1 application source remains in Git history and can be restored by checking out the commit before the root-replacement merge. Back up `data/jobs.db` and the media directory before a rollback; v2's additive schema may not be readable by old v1 code after startup migration.

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `YTPI_HOST` / `YTPI_PORT` | `0.0.0.0` / `7434` | Listen address/port inside the app/container. |
| `YTPI_HOST_PORT` | `7434` | Host port used by the root Docker service. |
| `YTPI_IMAGE_TAG` | `latest` | Public GHCR image tag to deploy; can be pinned to a commit-specific tag. |
| `YTPI_ALLOWED_CIDRS` | localhost and private IPv4 ranges | Addresses allowed to reach every route, including probes. Set narrowly for your network. |
| `YTPI_TRUST_PROXY` | `0` | Trust the first `X-Forwarded-For` address. Enable only behind a trusted proxy. |
| `YTPI_BLOCK_PRIVATE_URLS` | `0` | Reject literal private/reserved IP source URLs; does not resolve hostnames. |
| `YTPI_WRITE_AUTO_SUBS` | `0` | Fetch/convert English auto-captions. Optional because YouTube subtitle requests can be rate-limited independently of video downloads. |
| `YTPI_MAX_WORKERS` | `1` | Concurrent downloader worker count; `0` disables workers. |
| `YTPI_MAX_QUEUE_SIZE` | `200` | Maximum active jobs. |
| `YTPI_JOB_TIMEOUT_SECONDS` | `3600` | Per-job timeout in seconds. |
| `YTPI_MAX_RETRIES` | `1` | Automatic retries after yt-dlp failure. |
| `YTPI_ENABLE_REMOTE_COMPONENTS` | `1` | Allow yt-dlp's `ejs:github` remote component (requires network and Deno). |
| `YTPI_ENABLE_SHARE_GET` | `1` | Enable the legacy `/share` shortcut route. |
| `YTPI_SHARE_TOKEN` | empty | Required to use `/share`; configure a strong token or disable the route. |
| `YTPI_HOST_DOWNLOADS_DIR` | `/mnt/usb0/samsung/media/YouTube` | Host media directory mounted into the container. |

The app is intended for a trusted LAN. CIDR access control alone is not authentication; use a properly configured authenticated reverse proxy before any access beyond that network.

## API overview

All routes are subject to the CIDR allowlist.

- `POST /api/jobs` — queue one URL or an array of URLs; JSON body supports `url`/`urls`, `quality`, `category`/`custom_category`, `audio_only`, and `audio_format`.
- `GET /api/jobs?limit=40&offset=0&status=&search=` — paginated history plus full-history status counts.
- `GET /api/jobs/<id>` — job details and technical output.
- `POST /api/jobs/<id>/cancel` and `/retry` — stop or requeue an eligible job.
- `DELETE /api/jobs/completed` — remove finished/error/cancelled history only; media files remain.
- `GET /api/playlists`, `PUT /api/playlists/<id>`, `POST /api/playlists/<id>/sync` — saved playlist operations.
- `GET /healthz` and `/readyz` — liveness and readiness probes.
- `GET /share?url=...&token=...` — optional token-protected Shortcut integration.

## Project structure

- `ytpi_app/config.py` — validated settings, network access, URL/category handling.
- `ytpi_app/repository.py` — SQLite persistence and additive v1 schema migration.
- `ytpi_app/manager.py` — persistent queue, worker threads, yt-dlp subprocess lifecycle.
- `ytpi_app/__init__.py` — Flask app factory, access control, routes.
- `templates/index.html` and `static/` — responsive Material 3–inspired interface and client behavior.
- `scripts/migrate_v1_database.py` — read-only-source database copy/migration.
- `tests/` — API, persistence, migration, playlist, and network-guard tests.

## Design and accessibility

The interface uses tonal Material 3 surfaces and color roles, Google-blue emphasis, responsive navigation and cards, keyboard-visible focus, accessible field names and progress bars, reduced-motion support, light/dark themes, and touch-sized controls. Playlist and job metadata are built with DOM text nodes rather than interpolated HTML.

## Upgrade and rollback notes

The Docker workflow backs up the current SQLite database to `.deployment-backups/` before each deployment and migrates its schema additively in place. Keep a backup until you confirm v2 displays the expected job history and can download to the configured media folder. The existing external media folder is mounted in place; no media copy is required.

To roll back, stop v2 first, restore a pre-v2 database backup, then check out the previous v1 commit and redeploy. Do not start v1 against a database already migrated by v2; the v1 code may not understand the added columns. Preserve downloaded media throughout rollback.
