#!/usr/bin/env python3
"""Create an additive-migrated v2 copy of a stopped v1 SQLite database."""
from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path
from urllib.parse import quote

from ytpi_app.repository import JobRepository


def migrate_database(source: Path, destination: Path) -> tuple[int, int]:
    source = source.expanduser().resolve(strict=True)
    destination = destination.expanduser().resolve()
    if not source.is_file():
        raise ValueError("The source database must be a file.")
    if source == destination:
        raise ValueError("Source and destination must be different files.")
    if destination.exists():
        raise FileExistsError(f"Destination already exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    source_uri = f"file:{quote(str(source))}?mode=ro"
    try:
        with sqlite3.connect(source_uri, uri=True) as src, sqlite3.connect(destination) as dst:
            integrity = src.execute("PRAGMA quick_check").fetchone()[0]
            if integrity != "ok":
                raise sqlite3.DatabaseError(f"Source integrity check failed: {integrity}")
            src.backup(dst)
        repository = JobRepository(destination)
        try:
            job_count = repository.list_jobs(limit=1)[1]
            playlist_count = len(repository.list_playlists())
            if not repository.health_check():
                raise sqlite3.DatabaseError("Migrated database failed its health check.")
        finally:
            repository.close()
        return job_count, playlist_count
    except Exception:
        if destination.exists():
            destination.unlink()
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="Stopped v1 SQLite database (read-only input)")
    parser.add_argument("destination", type=Path, help="New v2 database path; must not already exist")
    args = parser.parse_args()
    jobs, playlists = migrate_database(args.source, args.destination)
    print(f"Created v2 database copy: {jobs} jobs, {playlists} playlists.")
    print("The source database was opened read-only and was not modified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
