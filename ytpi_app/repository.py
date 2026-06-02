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

    def list_jobs(self, *, limit: int, offset: int, status: str = "") -> tuple[list[dict[str, Any]], int]:
        safe_limit = max(1, min(limit, 500))
        safe_offset = max(0, offset)
        where = ""
        params: list[Any] = []
        if status:
            where = "WHERE status = ?"
            params.append(status)

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
