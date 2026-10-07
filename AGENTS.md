# YTPI v2 repository guidance

## Commands
- Install locally: `python3 -m venv .venv && .venv/bin/python -m pip install -r requirements.txt`.
- Run local development: `.venv/bin/python app.py` (port 7434 by default).
- Run all tests: `.venv/bin/python -m pytest -q`.
- Validate/deploy Docker: `docker compose config --quiet`, `docker compose up -d --build`; health probes are `/healthz` and `/readyz`.

## Project structure
- `app.py` and `ytpi_app/` are the Flask v2 application.
- `ytpi_app/config.py` owns validated settings/network/url handling; `repository.py` owns SQLite migrations/persistence; `manager.py` owns queued workers and yt-dlp.
- `static/` and `templates/` implement the responsive Material 3 interface.
- `.github/workflows/docker-workflow.yml` deploys the root Compose application to a self-hosted host on manual dispatch.

## Data and deployment invariants
- Keep the root Compose service/container name `ytpi`, internal port 7434, `./data:/app/data`, and the existing host media directory setting intact unless deliberately coordinating a migration.
- The v2 repository performs additive schema updates on the mounted SQLite database. Back up `data/jobs.db` before any root deployment; do not run v1 and v2 concurrently against the same DB.
- The deployment workflow must preserve the deployment `.env` and `data/`, and keep the existing fixed-container-name cleanup before Compose startup.
- Never commit `.env`, SQLite data, downloaded media, virtualenvs, or generated caches.
- Every route, including health checks, stays behind the configured CIDR allowlist. Only trust forwarded client IP headers behind a trusted proxy.
