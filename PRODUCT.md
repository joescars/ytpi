# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

People in a household or trusted local network who want to queue YouTube videos or playlists and manage downloaded media without needing technical expertise.

## Product Purpose

YTPI provides a private, local-network interface for queuing and managing YouTube video and audio downloads. Success means household members can use it easily and can understand what is happening while downloads run.

## Positioning

The confirmed product emphasis is ease of use for non-technical people, with clear, timely download progress. Whether this is a meaningfully distinct mechanism compared with other download managers remains undecided.

## Operating Context

People submit one or more HTTP(S) video or playlist links through a web interface. They choose video quality or audio format and a destination category, then monitor progress and manage jobs. Saved playlist settings can be synced. Job history and playlist settings persist in SQLite; media is saved to the configured local download directory. The app is intended for a household or trusted LAN, not direct public-internet exposure.

## Capabilities and Constraints

- Queue single or multiple video and playlist links.
- Download video at available quality or selected resolutions (4K, 2K, 1080p, 720p, 480p), or extract MP3/WAV audio.
- View progress, stage, speed, errors, and technical output; search and filter job history.
- Cancel queued or active jobs, retry failed or cancelled jobs, and remove terminal job history without deleting media.
- Save playlist settings, request playlist syncs, and inspect sync state.
- Uses Flask, SQLite, yt-dlp, and ffmpeg; can run locally or in Docker.
- Every route, including health checks, is subject to a configurable CIDR allowlist. Forwarded client IP headers are trusted only when explicitly configured behind a trusted proxy. CIDR access control is not user authentication; use an authenticated reverse proxy for access beyond the trusted LAN.
- Preserve the existing `ytpi` Compose service/container name, internal port 7434, `./data:/app/data` database mount, and configured host media directory unless coordinating a migration. Back up `data/jobs.db` before deployment; do not run v1 and v2 simultaneously against the same database.
- Whether the product is intended for use beyond a single household or trusted LAN is undecided.

## Evidence on Hand

- `README.md` documents current features, local development, API routes, configuration, Docker deployment, migration, and rollback procedures.
- `ytpi_app/`, `templates/`, and `static/` contain the Flask application, job/playlist workflows, and responsive web interface.
- No user testimonials, customer case studies, or independently verified performance claims were supplied; future work must not invent them.

## Product Principles

- Make common download tasks usable by people without technical expertise.
- Keep download state and progress understandable while work is running.
- Keep media and job history under the household's local control.
- Preserve history and downloaded media across upgrades and recovery operations.
- Enforce network access constraints consistently across application and health routes.
