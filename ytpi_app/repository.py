import json
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from .config import utc_now


class JobRepository:
    def __init__(self, db_path: Path):
        self._lock = threading.RLock()
        self._db_path = db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=NORMAL")
        self._init_schema()

    def _init_schema(self) -> None:
        with self._lock:
            self.conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    url TEXT NOT NULL,
                    status TEXT NOT NULL,
                    category TEXT NOT NULL DEFAULT '',
                    quality TEXT NOT NULL DEFAULT 'max',
                    audio_only INTEGER NOT NULL DEFAULT 0,
                    audio_format TEXT NOT NULL DEFAULT '',
                    output TEXT NOT NULL DEFAULT '',
                    error TEXT,
                    progress REAL,
                    eta TEXT,
                    speed TEXT,
                    filename TEXT,
                    attempt_count INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    started_at TEXT,
                    finished_at TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
                CREATE INDEX IF NOT EXISTS idx_jobs_created_at ON jobs(created_at);
                CREATE TABLE IF NOT EXISTS playlists (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    url TEXT NOT NULL UNIQUE,
                    name TEXT NOT NULL,
                    category TEXT NOT NULL DEFAULT '',
                    quality TEXT NOT NULL DEFAULT 'max',
                    audio_only INTEGER NOT NULL DEFAULT 0,
                    audio_format TEXT NOT NULL DEFAULT '',
                    last_synced_at TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    sync_status TEXT NOT NULL DEFAULT 'idle',
                    sync_job_id TEXT,
                    last_successful_sync_at TEXT,
                    discovered_count INTEGER,
                    downloaded_count INTEGER,
                    already_present_count INTEGER,
                    failed_count INTEGER,
                    last_sync_result TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_playlists_updated_at ON playlists(updated_at);
                """
            )
            for col, definition in [("audio_only", "INTEGER NOT NULL DEFAULT 0"), ("audio_format", "TEXT NOT NULL DEFAULT ''")]:
                try:
                    self.conn.execute(f"ALTER TABLE jobs ADD COLUMN {col} {definition}")
                except sqlite3.OperationalError:
                    pass
            self.conn.commit()

    def reset_stale_downloading_jobs(self) -> None:
        with self._lock:
            now = utc_now()
            self.conn.execute(
                """
                UPDATE jobs
                SET status='queued', updated_at=?, error=COALESCE(error,'')
                WHERE status='downloading'
                """,
                (now,),
            )
            self.conn.commit()

    def create_job(self, job_id: str, url: str, category: str, quality: str, audio_only: bool = False, audio_format: str = "") -> None:
        with self._lock:
            now = utc_now()
            self.conn.execute(
                """
                INSERT INTO jobs (id, url, status, category, quality, audio_only, audio_format, created_at, updated_at)
                VALUES (?, ?, 'queued', ?, ?, ?, ?, ?, ?)
                """,
                (job_id, url, category, quality, 1 if audio_only else 0, audio_format, now, now),
            )
            self.conn.commit()

    def upsert_playlist(self, url: str, name: str, category: str, quality: str, audio_only: bool = False, audio_format: str = "") -> dict[str, Any]:
        with self._lock:
            now = utc_now()
            # Check if playlist already exists
            existing = self.conn.execute(
                "SELECT name FROM playlists WHERE url = ?", (url,)
            ).fetchone()
            
            if existing:
                existing_name = existing["name"]
                # Determine if we should update the name
                # Rule: Don't overwrite real title with playlist ID, but do update with newer real title
                should_update_name = True
                
                # Check if existing name looks like a playlist ID (starts with PL and is alphanumeric)
                def is_playlist_id(name: str) -> bool:
                    return name.startswith("PL") and all(c.isalnum() or c == '_' for c in name)
                
                if is_playlist_id(existing_name) and not is_playlist_id(name):
                    # Existing is playlist ID, new is real title → update
                    should_update_name = True
                elif not is_playlist_id(existing_name) and is_playlist_id(name):
                    # Existing is real title, new is playlist ID → don't update
                    should_update_name = False
                elif not is_playlist_id(existing_name) and not is_playlist_id(name):
                    # Both are real titles → update (allow newer title)
                    should_update_name = True
                else:
                    # Both are playlist IDs → update (shouldn't happen but be safe)
                    should_update_name = True
                
                if should_update_name:
                    self.conn.execute(
                        """
                        INSERT INTO playlists (url, name, category, quality, audio_only, audio_format, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(url) DO UPDATE SET name=excluded.name, category=excluded.category,
                            quality=excluded.quality, audio_only=excluded.audio_only, audio_format=excluded.audio_format,
                            updated_at=excluded.updated_at
                        """,
                        (url, name, category, quality, 1 if audio_only else 0, audio_format, now, now),
                    )
                else:
                    # Update everything except name
                    self.conn.execute(
                        """
                        INSERT INTO playlists (url, name, category, quality, audio_only, audio_format, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(url) DO UPDATE SET category=excluded.category,
                            quality=excluded.quality, audio_only=excluded.audio_only, audio_format=excluded.audio_format,
                            updated_at=excluded.updated_at
                        """,
                        (url, name, category, quality, 1 if audio_only else 0, audio_format, now, now),
                    )
            else:
                # New playlist, always insert with given name
                self.conn.execute(
                    """
                    INSERT INTO playlists (url, name, category, quality, audio_only, audio_format, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(url) DO UPDATE SET name=excluded.name, category=excluded.category,
                        quality=excluded.quality, audio_only=excluded.audio_only, audio_format=excluded.audio_format,
                        updated_at=excluded.updated_at
                    """,
                    (url, name, category, quality, 1 if audio_only else 0, audio_format, now, now),
                )
            self.conn.commit()
            row = self.conn.execute("SELECT * FROM playlists WHERE url = ?", (url,)).fetchone()
        return dict(row)

    def list_playlists(self) -> list[dict[str, Any]]:
        with self._lock:
            rows = self.conn.execute("SELECT * FROM playlists ORDER BY updated_at DESC").fetchall()
        return [dict(row) for row in rows]

    def get_playlist(self, playlist_id: int) -> Optional[dict[str, Any]]:
        with self._lock:
            row = self.conn.execute("SELECT * FROM playlists WHERE id = ?", (playlist_id,)).fetchone()
        return dict(row) if row else None

    def get_playlist_by_url(self, url: str) -> Optional[dict[str, Any]]:
        with self._lock:
            row = self.conn.execute("SELECT * FROM playlists WHERE url = ?", (url,)).fetchone()
        return dict(row) if row else None

    def mark_playlist_synced(self, playlist_id: int) -> None:
        with self._lock:
            now = utc_now()
            self.conn.execute("UPDATE playlists SET last_synced_at=?, updated_at=? WHERE id=?", (now, now, playlist_id))
            self.conn.commit()

    def update_playlist_name(self, url: str, name: str) -> None:
        with self._lock:
            self.conn.execute("UPDATE playlists SET name=?, updated_at=? WHERE url=?", (name, utc_now(), url))
            self.conn.commit()

    def update_playlist_settings(self, playlist_id: int, category: str, quality: str, audio_only: bool, audio_format: str) -> None:
        """Update playlist settings without changing the name."""
        with self._lock:
            self.conn.execute(
                "UPDATE playlists SET category=?, quality=?, audio_only=?, audio_format=?, updated_at=? WHERE id=?",
                (category, quality, 1 if audio_only else 0, audio_format, utc_now(), playlist_id)
            )
            self.conn.commit()

    def update_playlist_sync_state(
        self,
        playlist_id: int,
        sync_status: str,
        sync_job_id: Optional[str] = None,
        last_successful_sync_at: Optional[str] = None,
    ) -> None:
        """Update playlist sync state and related fields."""
        with self._lock:
            now = utc_now()
            set_clauses = ["sync_status = ?", "updated_at = ?"]
            params = [sync_status, now]
            
            if sync_job_id is not None:
                set_clauses.append("sync_job_id = ?")
                params.append(sync_job_id)
            
            if last_successful_sync_at is not None:
                set_clauses.append("last_successful_sync_at = ?")
                params.append(last_successful_sync_at)
            
            # Update last_synced_at for backward compatibility (only on successful sync)
            if sync_status == "successful":
                set_clauses.append("last_synced_at = ?")
                if last_successful_sync_at is not None:
                    params.append(last_successful_sync_at)
                else:
                    params.append(now)
            
            params.append(str(playlist_id))
            query = f"UPDATE playlists SET {', '.join(set_clauses)} WHERE id = ?"
            self.conn.execute(query, params)
            self.conn.commit()

    def update_playlist_sync_results(
        self,
        playlist_id: int,
        discovered_count: int,
        downloaded_count: int,
        already_present_count: int,
        failed_count: int,
        last_sync_result: Optional[dict] = None,
    ) -> None:
        """Update playlist sync result counts."""
        with self._lock:
            now = utc_now()
            set_clauses = [
                "discovered_count = ?",
                "downloaded_count = ?", 
                "already_present_count = ?",
                "failed_count = ?",
                "updated_at = ?"
            ]
            params = [
                discovered_count,
                downloaded_count,
                already_present_count,
                failed_count,
                now
            ]
            
            if last_sync_result is not None:
                set_clauses.append("last_sync_result = ?")
                params.append(json.dumps(last_sync_result))
            
            params.append(str(playlist_id))
            query = f"UPDATE playlists SET {', '.join(set_clauses)} WHERE id = ?"
            self.conn.execute(query, params)
            self.conn.commit()

    def get_job(self, job_id: str) -> Optional[dict[str, Any]]:
        with self._lock:
            row = self.conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        return dict(row) if row else None

    def update_job(self, job_id: str, **fields: Any) -> None:
        if not fields:
            return
        fields["updated_at"] = utc_now()
        columns = ", ".join(f"{k} = ?" for k in fields)
        values = list(fields.values()) + [job_id]
        with self._lock:
            self.conn.execute(f"UPDATE jobs SET {columns} WHERE id = ?", values)
            self.conn.commit()

    def update_job_if_status_in(self, job_id: str, allowed_statuses: set[str], **fields: Any) -> bool:
        """Atomically update a job only if its current status is one of allowed_statuses.

        Returns True if the update applied. Used to avoid check-then-act races between
        cancellation and the worker loop transitioning a job to 'downloading'.
        """
        fields["updated_at"] = utc_now()
        columns = ", ".join(f"{k} = ?" for k in fields)
        values = list(fields.values()) + [job_id]
        where = f"status IN ({', '.join('?' for _ in allowed_statuses)})"
        values = values + list(allowed_statuses)
        with self._lock:
            self.conn.execute(f"UPDATE jobs SET {columns} WHERE id = ? AND {where}", values)
            self.conn.commit()
            return self.conn.total_changes > 0

    def get_downloading_jobs(self) -> list[dict[str, Any]]:
        with self._lock:
            rows = self.conn.execute("SELECT * FROM jobs WHERE status='downloading'").fetchall()
        return [dict(row) for row in rows]

    def list_jobs(self, limit: int = 200) -> list[dict[str, Any]]:
        with self._lock:
            rows = self.conn.execute(
                "SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(row) for row in rows]

    def list_terminal_jobs(self) -> list[dict[str, Any]]:
        with self._lock:
            rows = self.conn.execute(
                "SELECT * FROM jobs WHERE status IN ('finished', 'error', 'cancelled') ORDER BY finished_at DESC"
            ).fetchall()
        return [dict(row) for row in rows]

    def clear_terminal_jobs(self) -> int:
        with self._lock:
            self.conn.execute(
                "DELETE FROM jobs WHERE status IN ('finished', 'error', 'cancelled')"
            )
            self.conn.commit()
            return self.conn.total_changes

    def get_queued_job_ids(self) -> list[str]:
        with self._lock:
            rows = self.conn.execute("SELECT id FROM jobs WHERE status='queued' ORDER BY created_at").fetchall()
        return [row["id"] for row in rows]

    def list_pending_ids(self) -> list[str]:
        """Get IDs of queued jobs (alias for get_queued_job_ids for backward compatibility)."""
        return self.get_queued_job_ids()

    def count_active(self) -> int:
        """Count active (queued + downloading) jobs."""
        with self._lock:
            row = self.conn.execute(
                "SELECT COUNT(*) as count FROM jobs WHERE status IN ('queued', 'downloading')"
            ).fetchone()
        return row["count"] if row else 0

    def prune_terminal_jobs(self, retention_hours: int, max_history_jobs: int) -> None:
        """Prune old terminal jobs."""
        with self._lock:
            # First, limit total number of terminal jobs
            if max_history_jobs > 0:
                # Count terminal jobs
                terminal_count = self.conn.execute(
                    "SELECT COUNT(*) as count FROM jobs WHERE status IN ('finished', 'error', 'cancelled')"
                ).fetchone()["count"]
                
                if terminal_count > max_history_jobs:
                    # Delete oldest terminal jobs exceeding limit
                    self.conn.execute(
                        """
                        DELETE FROM jobs 
                        WHERE id IN (
                            SELECT id FROM jobs 
                            WHERE status IN ('finished', 'error', 'cancelled') 
                            ORDER BY finished_at ASC 
                            LIMIT ?
                        )
                        """,
                        (terminal_count - max_history_jobs,)
                    )
            
            # Then, delete jobs older than retention period
            if retention_hours > 0:
                cutoff = (datetime.now(timezone.utc) - timedelta(hours=retention_hours)).isoformat()
                self.conn.execute(
                    "DELETE FROM jobs WHERE status IN ('finished', 'error', 'cancelled') AND finished_at < ?",
                    (cutoff,)
                )
            
            self.conn.commit()

    def get_jobs_summary(self) -> dict[str, int]:
        with self._lock:
            rows = self.conn.execute(
                """
                SELECT status, COUNT(*) as count
                FROM jobs
                GROUP BY status
                """
            ).fetchall()
        return {row["status"]: row["count"] for row in rows}