import sqlite3

import pytest

from scripts.migrate_v1_database import migrate_database
from ytpi_app.repository import JobRepository


def test_migration_copies_legacy_rows_and_leaves_source_unchanged(tmp_path):
    source = tmp_path / "v1.db"
    destination = tmp_path / "v2" / "jobs.db"
    connection = sqlite3.connect(source)
    connection.executescript("""
        CREATE TABLE jobs (id TEXT PRIMARY KEY,url TEXT NOT NULL,status TEXT NOT NULL,category TEXT NOT NULL DEFAULT '',
          quality TEXT NOT NULL DEFAULT 'max',audio_only INTEGER NOT NULL DEFAULT 0,audio_format TEXT NOT NULL DEFAULT '',
          output TEXT NOT NULL DEFAULT '',error TEXT,progress REAL,eta TEXT,speed TEXT,filename TEXT,attempt_count INTEGER NOT NULL DEFAULT 0,
          created_at TEXT NOT NULL,updated_at TEXT NOT NULL,started_at TEXT,finished_at TEXT,title TEXT DEFAULT '',
          progress_stage TEXT DEFAULT '',playlist_item_position INTEGER,playlist_item_total INTEGER);
        CREATE TABLE playlists (id INTEGER PRIMARY KEY AUTOINCREMENT,url TEXT NOT NULL UNIQUE,name TEXT NOT NULL,
          category TEXT NOT NULL DEFAULT '',quality TEXT NOT NULL DEFAULT 'max',audio_only INTEGER NOT NULL DEFAULT 0,
          audio_format TEXT NOT NULL DEFAULT '',last_synced_at TEXT,created_at TEXT NOT NULL,updated_at TEXT NOT NULL);
        INSERT INTO jobs (id,url,status,created_at,updated_at,title,progress_stage)
          VALUES ('preserved-1','https://youtu.be/example','finished','2025-01-01','2025-01-02','Saved title','Finished');
        INSERT INTO playlists (url,name,created_at,updated_at)
          VALUES ('https://www.youtube.com/playlist?list=PL_A','Playlist A','2025-01-01','2025-01-02');
    """)
    connection.commit()
    connection.close()

    jobs, playlists = migrate_database(source, destination)

    assert (jobs, playlists) == (1, 1)
    source_conn = sqlite3.connect(source)
    assert source_conn.execute("PRAGMA quick_check").fetchone()[0] == "ok"
    assert "stage" not in {row[1] for row in source_conn.execute("PRAGMA table_info(jobs)")}
    source_conn.close()
    repository = JobRepository(destination)
    assert repository.get_job("preserved-1")["title"] == "Saved title"
    assert repository.get_job("preserved-1")["stage"] == "Finished"
    assert repository.list_playlists()[0]["name"] == "Playlist A"
    repository.close()


def test_migration_refuses_to_overwrite_destination(tmp_path):
    source = tmp_path / "source.db"
    source.touch()
    destination = tmp_path / "already-there.db"
    destination.write_text("keep this file")

    with pytest.raises(FileExistsError):
        migrate_database(source, destination)

    assert destination.read_text() == "keep this file"
