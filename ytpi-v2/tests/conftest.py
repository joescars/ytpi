import pytest

from ytpi_app import create_app


@pytest.fixture

def app(tmp_path, monkeypatch):
    monkeypatch.setenv("YTPI_DB_PATH", str(tmp_path / "jobs.sqlite3"))
    monkeypatch.setenv("YTPI_DOWNLOADS_DIR", str(tmp_path / "downloads"))
    monkeypatch.setenv("YTPI_ALLOWED_CIDRS", "127.0.0.1/32")
    monkeypatch.setenv("YTPI_MAX_WORKERS", "0")
    application = create_app()
    application.config.update(TESTING=True)
    yield application
    application.extensions["ytpi_repository"].close()


@pytest.fixture

def client(app):
    return app.test_client()
