# YTPI v2

A private, responsive YouTube download manager for your home network. v2 is being rebuilt in a separate folder and can be previewed alongside the existing YTPI installation. It uses Flask, SQLite, yt-dlp, ffmpeg, and a Material 3–inspired responsive web interface.

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
set -a; . ./.env; set +a
YTPI_PORT="${YTPI_HOST_PORT:-7435}" .venv/bin/python app.py
```

Open <http://localhost:7435>. For development, set `YTPI_MAX_WORKERS=0` to prevent queued jobs from starting. Settings come from environment variables; see `.env.example`. Do not expose the service directly to the public internet. The CIDR allowlist is network access control, not user authentication.

Run tests:

```bash
.venv/bin/python -m pytest -q
```

## Side-by-side Docker preview

The v2 Compose stack is deliberately named `ytpi-v2`, stores state under this project's `data/` and `downloads/` directories by default, and publishes port **7435** so the current v1 port is not replaced. The default host bind address is `0.0.0.0` so other devices on your LAN can reach it; the app's CIDR allowlist still applies. Use `YTPI_HOST_BIND_ADDRESS` to bind to a specific interface if preferred.

```bash
cp .env.example .env
docker compose up -d --build
docker compose ps
curl --fail http://localhost:7435/healthz
curl --fail http://localhost:7435/readyz
```

Open <http://localhost:7435> on the server. From another device on the same LAN, open `http://<server-LAN-IPv4>:7435` (for this server, currently `http://192.168.68.121:7435`). The YTPI CIDR allowlist includes private IPv4 LAN ranges by default. Stop only the v2 preview with `docker compose down`; this leaves its database and media directory intact. Do not run `docker compose down -v` if you want to keep that data.

To make v2 see the existing media without copying it, set `YTPI_HOST_DOWNLOADS_DIR` in v2's `.env` to the absolute v1 media directory. Review file permissions first. A shared media directory does not share the database or job history. Avoid running two applications against the same SQLite database.

## Copy v1 job and playlist history

**Stop v1 first and make a separate backup.** Do not point v2 directly at the live v1 SQLite database: v2 adds columns and both versions must not write the same database concurrently. The migration script makes an SQLite-consistent copy, checks its integrity, applies v2's additive schema migration to the copy, and reports the number of preserved job and playlist records. It does not modify the source and refuses to overwrite the destination.

```bash
.venv/bin/python scripts/migrate_v1_database.py /path/to/v1/data/jobs.db ./data/jobs.db
```

Use the actual database path configured for v1. Confirm the printed counts, then start v2. Downloaded media is independent: either keep v2's local `downloads/` directory or point `YTPI_HOST_DOWNLOADS_DIR` at v1's media directory. Do not delete the v1 database, media, or install as part of the preview.

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `YTPI_HOST` / `YTPI_PORT` | `0.0.0.0` / `7434` | Listen address/port inside the app/container. |
| `YTPI_HOST_PORT` | `7435` | Host port used by the side-by-side Compose preview. |
| `YTPI_ALLOWED_CIDRS` | localhost and private IPv4 ranges | Addresses allowed to reach every route, including probes. Set narrowly for your network. |
| `YTPI_TRUST_PROXY` | `0` | Trust the first `X-Forwarded-For` address. Enable only behind a trusted proxy. |
| `YTPI_BLOCK_PRIVATE_URLS` | `0` | Reject literal private/reserved IP source URLs; does not resolve hostnames. |
| `YTPI_MAX_WORKERS` | `1` | Concurrent downloader worker count; `0` disables workers. |
| `YTPI_MAX_QUEUE_SIZE` | `200` | Maximum active jobs. |
| `YTPI_JOB_TIMEOUT_SECONDS` | `3600` | Per-job timeout in seconds. |
| `YTPI_MAX_RETRIES` | `1` | Automatic retries after yt-dlp failure. |
| `YTPI_ENABLE_REMOTE_COMPONENTS` | `1` | Allow yt-dlp's `ejs:github` remote component (requires network and Deno). |
| `YTPI_ENABLE_SHARE_GET` | `1` | Enable the legacy `/share` shortcut route. |
| `YTPI_SHARE_TOKEN` | empty | Required to use `/share`; configure a strong token or disable the route. |
| `YTPI_HOST_DOWNLOADS_DIR` | `./downloads` | Host media directory mounted into the container. |

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

## Current v2 preview status

This is an active rebuild. Verify the flows you rely on in the side-by-side preview before replacing v1. In particular, validate yt-dlp behavior against a safe test video/playlist, confirm media permissions for any shared directory, and check imported history using a **copy** of the production database. No production cutover is performed by these instructions.
