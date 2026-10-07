from __future__ import annotations

import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class JobRepository:
    """SQLite persistence for jobs and saved playlists, including additive v1 migration."""

    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._connection = sqlite3.connect(path, check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA journal_mode=WAL")
        self._connection.execute("PRAGMA foreign_keys=ON")
        self._initialize()

    def _initialize(self) -> None:
        with self._lock:
            self._connection.executescript("""
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY, url TEXT NOT NULL, title TEXT NOT NULL DEFAULT '', status TEXT NOT NULL,
                    category TEXT NOT NULL DEFAULT '', quality TEXT NOT NULL DEFAULT 'max', audio_only INTEGER NOT NULL DEFAULT 0,
                    audio_format TEXT NOT NULL DEFAULT 'mp3', progress REAL NOT NULL DEFAULT 0,
                    stage TEXT NOT NULL DEFAULT 'Queued', speed TEXT NOT NULL DEFAULT '', eta TEXT NOT NULL DEFAULT '',
                    filename TEXT NOT NULL DEFAULT '', error TEXT NOT NULL DEFAULT '', output TEXT NOT NULL DEFAULT '',
                    attempt_count INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                    started_at TEXT, finished_at TEXT,
                    playlist_id INTEGER
                );
                CREATE TABLE IF NOT EXISTS playlists (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, url TEXT NOT NULL UNIQUE, name TEXT NOT NULL,
                    category TEXT NOT NULL DEFAULT '', quality TEXT NOT NULL DEFAULT 'max', audio_only INTEGER NOT NULL DEFAULT 0,
                    audio_format TEXT NOT NULL DEFAULT '', last_synced_at TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                    sync_status TEXT DEFAULT 'idle', sync_job_id TEXT, last_successful_sync_at TEXT,
                    discovered_count INTEGER DEFAULT 0, downloaded_count INTEGER DEFAULT 0,
                    already_present_count INTEGER DEFAULT 0, failed_count INTEGER DEFAULT 0
                );
            """)
            self._add_missing_columns("jobs", {
                "title": "TEXT NOT NULL DEFAULT ''", "category": "TEXT NOT NULL DEFAULT ''",
                "quality": "TEXT NOT NULL DEFAULT 'max'", "audio_only": "INTEGER NOT NULL DEFAULT 0",
                "audio_format": "TEXT NOT NULL DEFAULT 'mp3'", "progress": "REAL NOT NULL DEFAULT 0",
                "stage": "TEXT NOT NULL DEFAULT 'Queued'", "speed": "TEXT NOT NULL DEFAULT ''",
                "eta": "TEXT NOT NULL DEFAULT ''", "filename": "TEXT NOT NULL DEFAULT ''",
                "error": "TEXT NOT NULL DEFAULT ''", "output": "TEXT NOT NULL DEFAULT ''",
                "attempt_count": "INTEGER NOT NULL DEFAULT 0", "created_at": "TEXT NOT NULL DEFAULT ''",
                "updated_at": "TEXT NOT NULL DEFAULT ''",
                "started_at": "TEXT", "finished_at": "TEXT", "playlist_id": "INTEGER",
            })
            self._add_missing_columns("playlists", {
                "url": "TEXT NOT NULL DEFAULT ''", "name": "TEXT NOT NULL DEFAULT ''",
                "category": "TEXT NOT NULL DEFAULT ''", "quality": "TEXT NOT NULL DEFAULT 'max'",
                "audio_only": "INTEGER NOT NULL DEFAULT 0", "audio_format": "TEXT NOT NULL DEFAULT ''",
                "last_synced_at": "TEXT", "created_at": "TEXT NOT NULL DEFAULT ''", "updated_at": "TEXT NOT NULL DEFAULT ''",
                "sync_status": "TEXT DEFAULT 'idle'", "sync_job_id": "TEXT", "last_successful_sync_at": "TEXT",
                "discovered_count": "INTEGER DEFAULT 0", "downloaded_count": "INTEGER DEFAULT 0",
                "already_present_count": "INTEGER DEFAULT 0", "failed_count": "INTEGER DEFAULT 0",
            })
            columns = {row["name"] for row in self._connection.execute("PRAGMA table_info(jobs)")}
            if "progress_stage" in columns:
                self._connection.execute("UPDATE jobs SET stage=progress_stage WHERE stage='Queued' AND progress_stage IS NOT NULL AND progress_stage!=''")
            if "stage" in columns:
                self._connection.execute("UPDATE jobs SET stage='Downloading' WHERE status='downloading' AND stage='Queued'")
                self._connection.execute("UPDATE jobs SET stage='Finished' WHERE status='finished' AND stage='Queued'")
                self._connection.execute("UPDATE jobs SET stage='Failed' WHERE status='error' AND stage='Queued'")
                self._connection.execute("UPDATE jobs SET stage='Cancelled' WHERE status='cancelled' AND stage='Queued'")
            self._connection.execute("CREATE INDEX IF NOT EXISTS idx_jobs_created ON jobs(created_at DESC)")
            self._connection.execute("CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status)")
            self._connection.execute("CREATE INDEX IF NOT EXISTS idx_playlists_updated ON playlists(updated_at DESC)")
            self._connection.commit()

    def _add_missing_columns(self, table: str, columns: dict[str, str]) -> None:
        existing = {row["name"] for row in self._connection.execute(f"PRAGMA table_info({table})")}
        for name, definition in columns.items():
            if name not in existing:
                self._connection.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")

    def close(self) -> None:
        with self._lock:
            self._connection.close()

    def create_job(self, *, job_id: str, url: str, category: str, quality: str, audio_only: bool, audio_format: str, playlist_id: int | None = None) -> dict[str, Any]:
        now = now_iso()
        with self._lock:
            self._connection.execute("""INSERT INTO jobs
                (id,url,status,category,quality,audio_only,audio_format,created_at,updated_at,playlist_id)
                VALUES (?,?, 'queued', ?, ?, ?, ?, ?, ?, ?)""",
                (job_id, url, category, quality, int(audio_only), audio_format, now, now, playlist_id))
            self._connection.commit()
            job = self.get_job(job_id)
            assert job is not None
            return job

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._connection.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
            return dict(row) if row else None

    def list_jobs(self, *, limit: int = 100, offset: int = 0, status: str = "", search: str = "") -> tuple[list[dict[str, Any]], int]:
        clauses: list[str] = []
        params: list[Any] = []
        if status:
            clauses.append("status=?")
            params.append(status)
        if search:
            clauses.append("(title LIKE ? OR url LIKE ? OR id LIKE ? OR filename LIKE ?)")
            needle = f"%{search}%"
            params.extend([needle] * 4)
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        with self._lock:
            total = self._connection.execute(f"SELECT COUNT(*) FROM jobs{where}", params).fetchone()[0]
            rows = self._connection.execute(f"SELECT * FROM jobs{where} ORDER BY created_at DESC LIMIT ? OFFSET ?",
                                            [*params, max(1, min(limit, 200)), max(0, offset)]).fetchall()
        return [dict(row) for row in rows], int(total)

    def update_job(self, job_id: str, **fields: Any) -> None:
        if not fields:
            return
        fields["updated_at"] = now_iso()
        names = list(fields)
        with self._lock:
            self._connection.execute(f"UPDATE jobs SET {', '.join(f'{name}=?' for name in names)} WHERE id=?",
                                     [*(fields[name] for name in names), job_id])
            self._connection.commit()

    def prune_terminal_jobs(self, retention_hours: int, max_history_jobs: int) -> int:
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=retention_hours)).isoformat()
        terminal = "('finished','error','cancelled')"
        with self._lock:
            removed = self._connection.execute(f"DELETE FROM jobs WHERE status IN {terminal} AND updated_at < ?", (cutoff,)).rowcount
            excess = self._connection.execute("SELECT COUNT(*) FROM jobs WHERE status IN ('finished','error','cancelled')").fetchone()[0] - max_history_jobs
            if excess > 0:
                removed += self._connection.execute("""DELETE FROM jobs WHERE id IN (
                    SELECT id FROM jobs WHERE status IN ('finished','error','cancelled')
                    ORDER BY updated_at ASC LIMIT ?)""", (excess,)).rowcount
            self._connection.commit()
            return int(removed)

    def count_active(self) -> int:
        with self._lock:
            return int(self._connection.execute("SELECT COUNT(*) FROM jobs WHERE status IN ('queued','downloading')").fetchone()[0])

    def health_check(self) -> bool:
        try:
            with self._lock:
                self._connection.execute("SELECT 1").fetchone()
            return True
        except sqlite3.Error:
            return False

    def status_counts(self) -> dict[str, int]:
        with self._lock:
            rows = self._connection.execute("SELECT status,COUNT(*) AS count FROM jobs GROUP BY status").fetchall()
        return {str(row["status"]): int(row["count"]) for row in rows}

    def queued_jobs(self) -> list[str]:
        with self._lock:
            return [row[0] for row in self._connection.execute("SELECT id FROM jobs WHERE status='queued' ORDER BY created_at")]

    def recover_interrupted_jobs(self) -> list[str]:
        with self._lock:
            self._connection.execute("UPDATE jobs SET status='queued',stage='Queued',updated_at=? WHERE status='downloading'", (now_iso(),))
            self._connection.commit()
            return self.queued_jobs()

    def clear_finished(self) -> int:
        with self._lock:
            cursor = self._connection.execute("DELETE FROM jobs WHERE status IN ('finished','error','cancelled')")
            self._connection.commit()
            return cursor.rowcount

    def list_playlists(self) -> list[dict[str, Any]]:
        with self._lock:
            return [dict(row) for row in self._connection.execute("SELECT * FROM playlists ORDER BY updated_at DESC")]

    def get_playlist(self, playlist_id: int) -> dict[str, Any] | None:
        with self._lock:
            row = self._connection.execute("SELECT * FROM playlists WHERE id=?", (playlist_id,)).fetchone()
            return dict(row) if row else None

    def get_playlist_for_url(self, url: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._connection.execute("SELECT * FROM playlists WHERE url=?", (url,)).fetchone()
            return dict(row) if row else None

    def upsert_playlist(self, url: str, name: str, category: str, quality: str, audio_only: bool, audio_format: str) -> dict[str, Any]:
        from urllib.parse import parse_qs, urlparse
        now = now_iso()
        existing = self.get_playlist_for_url(url)
        playlist_key = parse_qs(urlparse(url).query).get("list", [""])[0]
        if existing and playlist_key and name == playlist_key:
            name = existing["name"]
        name = name or (existing["name"] if existing else url)
        with self._lock:
            self._connection.execute("""INSERT INTO playlists (url,name,category,quality,audio_only,audio_format,created_at,updated_at)
                VALUES (?,?,?,?,?,?,?,?) ON CONFLICT(url) DO UPDATE SET
                name=CASE WHEN excluded.name='' OR excluded.name=excluded.url THEN playlists.name ELSE excluded.name END,
                category=excluded.category,quality=excluded.quality,audio_only=excluded.audio_only,
                audio_format=excluded.audio_format,updated_at=excluded.updated_at""",
                (url,name,category,quality,int(audio_only),audio_format,now,now))
            self._connection.commit()
        result = self.get_playlist_for_url(url)
        assert result is not None
        return result

    def update_playlist_settings(self, playlist_id: int, category: str, quality: str, audio_only: bool, audio_format: str) -> None:
        with self._lock:
            self._connection.execute("UPDATE playlists SET category=?,quality=?,audio_only=?,audio_format=?,updated_at=? WHERE id=?",
                                     (category,quality,int(audio_only),audio_format,now_iso(),playlist_id))
            self._connection.commit()

    def update_playlist_name(self, url: str, name: str) -> None:
        if name:
            with self._lock:
                self._connection.execute("UPDATE playlists SET name=?,updated_at=? WHERE url=?", (name,now_iso(),url))
                self._connection.commit()

    def update_playlist_results(self, playlist_id: int, discovered: int, downloaded: int, existing: int, failed: int) -> None:
        with self._lock:
            self._connection.execute("UPDATE playlists SET discovered_count=?,downloaded_count=?,already_present_count=?,failed_count=?,updated_at=? WHERE id=?",
                                     (discovered,downloaded,existing,failed,now_iso(),playlist_id))
            self._connection.commit()


    def set_playlist_sync(self, playlist_id: int, status: str, job_id: str | None = None, success: bool = False) -> None:
        now = now_iso()
        with self._lock:
            self._connection.execute("""UPDATE playlists SET sync_status=?,sync_job_id=COALESCE(?,sync_job_id),
                last_successful_sync_at=CASE WHEN ? THEN ? ELSE last_successful_sync_at END,
                last_synced_at=CASE WHEN ? THEN ? ELSE last_synced_at END,updated_at=? WHERE id=?""",
                (status,job_id,int(success),now,int(success),now,now,playlist_id))
            self._connection.commit()

    def playlist_for_job(self, job_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._connection.execute("SELECT * FROM playlists WHERE sync_job_id=?", (job_id,)).fetchone()
            return dict(row) if row else None
