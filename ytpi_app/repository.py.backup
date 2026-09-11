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
                    updated_at TEXT NOT NULL
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
        if not fields:
            return False
        fields["updated_at"] = utc_now()
        columns = ", ".join(f"{k} = ?" for k in fields)
        placeholders = ", ".join("?" for _ in allowed_statuses)
        values = list(fields.values()) + [job_id] + list(allowed_statuses)
        with self._lock:
            cur = self.conn.execute(
                f"UPDATE jobs SET {columns} WHERE id = ? AND status IN ({placeholders})",
                values,
            )
            self.conn.commit()
        return cur.rowcount > 0

    def list_jobs(self, *, limit: int, offset: int, status: str = "", category: str = "", search: str = "") -> tuple[list[dict[str, Any]], int]:
        safe_limit = max(1, min(limit, 500))
        safe_offset = max(0, offset)
        where_parts = []
        params: list[Any] = []
        
        if status:
            where_parts.append("status = ?")
            params.append(status)
        if category:
            where_parts.append("category = ?")
            params.append(category)
        if search:
            where_parts.append("(title LIKE ? OR url LIKE ? OR filename LIKE ? OR id LIKE ?)")
            search_term = f"%{search}%"
            params.extend([search_term, search_term, search_term, search_term])
        
        where = ("WHERE " + " AND ".join(where_parts)) if where_parts else ""

        with self._lock:
            total = self.conn.execute(f"SELECT COUNT(*) AS c FROM jobs {where}", params).fetchone()["c"]
            rows = self.conn.execute(
                f"""
                SELECT * FROM jobs
                {where}
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
                """,
                params + [safe_limit, safe_offset],
            ).fetchall()
        return [dict(row) for row in rows], int(total)

    def list_pending_ids(self) -> list[str]:
        with self._lock:
            rows = self.conn.execute("SELECT id FROM jobs WHERE status = 'queued' ORDER BY created_at ASC").fetchall()
        return [row["id"] for row in rows]

    def count_active(self) -> int:
        with self._lock:
            row = self.conn.execute("SELECT COUNT(*) AS c FROM jobs WHERE status IN ('queued', 'downloading')").fetchone()
        return int(row["c"])

    def health_check(self) -> bool:
        try:
            with self._lock:
                self.conn.execute("SELECT 1")
            return True
        except sqlite3.Error:
            return False

    def prune_terminal_jobs(self, retention_hours: int, max_history_jobs: int) -> int:
        removed = 0
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=retention_hours)).isoformat()
        with self._lock:
            cur = self.conn.execute(
                """
                DELETE FROM jobs
                WHERE status IN ('finished','error','cancelled')
                  AND updated_at < ?
                """,
                (cutoff,),
            )
            removed += cur.rowcount

            row = self.conn.execute("SELECT COUNT(*) AS c FROM jobs").fetchone()
            total = int(row["c"])
            overflow = total - max_history_jobs
            if overflow > 0:
                cur = self.conn.execute(
                    """
                    DELETE FROM jobs
                    WHERE id IN (
                        SELECT id FROM jobs
                        WHERE status IN ('finished','error','cancelled')
                        ORDER BY updated_at ASC
                        LIMIT ?
                    )
                    """,
                    (overflow,),
                )
                removed += cur.rowcount
            self.conn.commit()
        return removed

    def clear_terminal_jobs(self) -> int:
        with self._lock:
            cur = self.conn.execute("DELETE FROM jobs WHERE status IN ('finished','error','cancelled')")
            removed = cur.rowcount
            self.conn.commit()
        return removed
