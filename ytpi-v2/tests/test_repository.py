import sqlite3

from ytpi_app.repository import JobRepository


def test_repository_opens_v1_database_without_dropping_job_history(tmp_path):
    database = tmp_path / "legacy.db"
    connection = sqlite3.connect(database)
    connection.execute("""CREATE TABLE jobs (
        id TEXT PRIMARY KEY, url TEXT NOT NULL, title TEXT DEFAULT '', status TEXT NOT NULL,
        category TEXT NOT NULL DEFAULT '', quality TEXT NOT NULL DEFAULT 'max', audio_only INTEGER DEFAULT 0,
        audio_format TEXT DEFAULT '', progress REAL, output TEXT DEFAULT '', error TEXT DEFAULT '',
        created_at TEXT NOT NULL, updated_at TEXT NOT NULL, progress_stage TEXT DEFAULT ''
    )""")
    connection.execute("INSERT INTO jobs (id,url,title,status,created_at,updated_at,progress_stage) VALUES ('legacy-1','https://youtu.be/example','Known title','finished','2025-01-01','2025-01-02','Finished')")
    connection.commit()
    connection.close()

    repository = JobRepository(database)
    job = repository.get_job("legacy-1")

    assert job["title"] == "Known title"
    assert job["status"] == "finished"
    assert job["stage"] == "Finished"
    repository.close()


def test_status_counts_are_aggregated_from_entire_history(tmp_path):
    repository = JobRepository(tmp_path / "jobs.db")
    repository.create_job(job_id="queued-1", url="https://youtu.be/one", category="", quality="max", audio_only=False, audio_format="mp3")
    repository.create_job(job_id="queued-2", url="https://youtu.be/two", category="", quality="max", audio_only=False, audio_format="mp3")

    assert repository.status_counts() == {"queued": 2}
    repository.close()
