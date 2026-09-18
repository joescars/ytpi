# Agent Instructions

## Commands

- Set up locally with `cp .env.example .env`, `python3 -m venv .venv`, `source .venv/bin/activate`, and `pip install -r requirements.txt`.
- Run the development server with `python app.py` at `http://localhost:7434`; production Docker uses `waitress` through `docker-entrypoint.sh`.
- Run the full test suite with `pytest -q`; run one test with `pytest -q tests/test_app.py::test_enqueue_download`.
- Build and run the container with `docker compose up -d --build`; compose persists downloads and SQLite data through bind mounts.
- There is no configured lint, formatter, typecheck, or codegen command.

## Structure

- `app.py` is the WSGI/dev entrypoint; `ytpi_app.create_app()` is the Flask factory.
- `ytpi_app/config.py` owns environment loading and validation, `repository.py` owns SQLite job persistence, `manager.py` owns the queue/workers and `yt-dlp` subprocesses, and `routes.py` wires the app and HTTP endpoints.
- `templates/` and `static/` are server-rendered Jinja2 UI assets with no frontend build step.
- Jobs persist in SQLite, are recovered from `queued` state on startup, and follow `queued -> downloading -> finished|error|cancelled`; do not assume job state is only in memory.

## Important Constraints

- Every request is subject to the CIDR allowlist in `YTPI_ALLOWED_CIDRS`; preserve this `before_request` security boundary. `YTPI_TRUST_PROXY=1` changes which client IP is read.
- Validate URLs, categories, quality, and audio format through the existing helpers; category paths must remain under `YTPI_DOWNLOADS_DIR`.
- Downloads invoke external `yt-dlp` and may require `ffmpeg`; `YTPI_ENABLE_REMOTE_COMPONENTS=1` also requires live GitHub access and a supported JavaScript runtime in Docker (`deno` is installed there).
- `YTPI_MAX_WORKERS=0` intentionally starts no workers and is used by tests; queued test jobs are not downloaded.

## Testing Quirks

- `tests/test_app.py` builds each app against temporary `YTPI_DOWNLOADS_DIR` and `YTPI_DB_PATH`, sets `YTPI_MAX_WORKERS=0`, and allowlists `127.0.0.1`.
- Flask test requests must pass `environ_base={"REMOTE_ADDR": "127.0.0.1"}` (or another configured address), otherwise the access guard returns `403`.
- Read `README.md` for the complete API/environment reference and current deployment notes.
