# ytpi

A Flask-based local YouTube downloader service using `yt-dlp`, designed for Raspberry Pi and LAN-only access by default.

## What Changed

This version adds:

- Persistent job history/queue in SQLite (`jobs.db`)
- Safer network allowlisting with CIDR support (`ipaddress`)
- Category path sanitization and traversal protection
- Worker timeout, retry, cancel, and retry endpoints
- Live dashboard updates (status table + output panel)
- Configurable runtime through environment variables
- Health/readiness endpoints: `/healthz`, `/readyz`
- Structured JSON logging
- Production container entrypoint via `waitress`

## Quick Start

```bash
cp .env.example .env
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

App URL: `http://localhost:7434`

## API

### Queue downloads

```bash
curl -X POST http://localhost:7434/download \
  -H "Content-Type: application/json" \
  -d '{"url":"https://youtube.com/watch?v=VIDEO_ID","quality":"1080","category":"Music"}'
```

`/download` also accepts standard form-encoded submission (`application/x-www-form-urlencoded`), which is what the web UI (`templates/index.html`) uses — the route branches on `request.is_json`. Form submissions redirect to `/status` on success instead of returning JSON.

Full set of accepted `/download` fields:

- `url` (string) or `urls` (array) — one or more video URLs. `url` also accepts a single newline/comma-separated string for multiple URLs.
- `quality` — one of `max`, `2160`, `1440`, `1080`, `720`, `480` (default `max`)
- `category` — destination subfolder under `YTPI_DOWNLOADS_DIR`; pass `__custom__` with `customCategory` set to create/use an arbitrary sanitized name
- `customCategory` — required when `category` is `__custom__`
- `audio_only` — `true`/`1`/`yes`/`on` to extract audio only (always filed under the `audio-only` category)
- `audio_format` — `mp3` or `wav` (default `mp3`), only used when `audio_only` is set

Example audio-only request:

```bash
curl -X POST http://localhost:7434/download \
  -H "Content-Type: application/json" \
  -d '{"url":"https://youtube.com/watch?v=VIDEO_ID","audio_only":true,"audio_format":"mp3"}'
```

### Status

- UI: `GET /status`
- JSON list: `GET /api/status?limit=200&offset=0&status=`
- Output: `GET /job_output/<job_id>`

### Job control

- Cancel: `POST /jobs/<job_id>/cancel`
- Retry: `POST /jobs/<job_id>/retry`
- Clear terminal jobs: `POST /clear-finished`

### Probes

- Liveness: `GET /healthz`
- Readiness: `GET /readyz`

## Share Sheet Endpoint

`GET /share` still exists for iOS shortcut compatibility, but is configurable:

- `YTPI_ENABLE_SHARE_GET=0` disables it
- `YTPI_SHARE_TOKEN=<token>` requires `?token=<token>`

Example:

```bash
curl "http://localhost:7434/share?url=https://youtube.com/watch?v=VIDEO_ID&token=YOUR_TOKEN"
```

## Configuration

Copy `.env.example` and override as needed:

- `YTPI_HOST` (default `0.0.0.0`)
- `YTPI_PORT` (default `7434`)
- `YTPI_DOWNLOADS_DIR` (default `./downloads`)
- `YTPI_DB_PATH` (default `./jobs.db`)
- `YTPI_ALLOWED_CIDRS` (default private/local CIDRs)
- `YTPI_TRUST_PROXY` (`0|1`)
- `YTPI_ENABLE_SHARE_GET` (`0|1`)
- `YTPI_SHARE_TOKEN` (optional)
- `YTPI_MAX_QUEUE_SIZE` (default `200`)
- `YTPI_MAX_WORKERS` (default `1`)
- `YTPI_JOB_TIMEOUT_SECONDS` (default `3600`)
- `YTPI_MAX_RETRIES` (default `1`)
- `YTPI_MAX_OUTPUT_CHARS` (default `8000`)
- `YTPI_JOB_RETENTION_HOURS` (default `168`)
- `YTPI_MAX_HISTORY_JOBS` (default `2000`)
- `YTPI_FFMPEG_PATH` (optional)
- `YTPI_YTDLP_BIN` (default `yt-dlp`)
- `YTPI_ENABLE_REMOTE_COMPONENTS` (`0|1`, default `1`) — controls whether yt-dlp is invoked with `--remote-components ejs:github`. This is currently needed for YouTube's JS-challenge bypass but means every job depends on live GitHub access; disable if you'd rather fail closed than depend on that.
- `YTPI_BLOCK_PRIVATE_URLS` (`0|1`, default `0`) — when enabled, rejects submitted URLs whose host is a literal private/loopback/link-local/reserved IP address (basic SSRF mitigation; does not perform DNS resolution, so a hostname that merely *resolves* to an internal address is not caught)
- `YTPI_MAX_CONTENT_LENGTH` (default `65536`) — max request body size in bytes accepted by Flask

## Docker

```bash
docker compose up -d --build
```

Default compose publishes `7434:7434`, persists downloads and SQLite data, and includes health checks. Downloads are bind-mounted to `./downloads` by default — override with `YTPI_HOST_DOWNLOADS_DIR=/path/to/media docker compose up -d` (e.g. to point at a USB drive or NAS mount) or edit `docker-compose.yml` directly.

`docker-entrypoint.sh` runs the app under [`waitress`](https://github.com/Pylons/waitress), a production WSGI server; `python app.py` (used in Quick Start / Dev Container) uses Flask's built-in development server and is not intended for anything beyond local development. If you run bare-metal outside Docker, put `waitress-serve --listen=0.0.0.0:7434 app:app` (or another production WSGI server) in front instead.

## Security Notes

- All requests are restricted by CIDR allowlist (`YTPI_ALLOWED_CIDRS`)
- Category names are sanitized and constrained to the downloads root
- Optional share token for `GET /share`

## Testing

```bash
pytest -q
```

## Local Development Notes

- The app enforces CIDR allowlisting on every request.
- Default `YTPI_ALLOWED_CIDRS` already allows localhost/private ranges.
- If you are testing through a proxy/tunnel, set:

```bash
export YTPI_TRUST_PROXY=1
```

- If your local network path is unusual, adjust:

```bash
export YTPI_ALLOWED_CIDRS="127.0.0.0/8,::1/128,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16"
```

## Dev Container

Use the provided `.devcontainer` config in VS Code, then run:

```bash
python app.py
```

And for tests:

```bash
pytest -q
```

Port `7434` is auto-forwarded by the dev container config.

## Deploy Workflows

GitHub actions are provided for self-hosted deployment and now include automated test execution before restart/build.
