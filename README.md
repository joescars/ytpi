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

For multiple URLs, pass `url` as newline/comma-separated string or `urls` as array.

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

## Docker

```bash
docker compose up -d --build
```

Default compose publishes `7434:7434`, persists downloads and SQLite data, and includes health checks.

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
