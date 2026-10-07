from dataclasses import replace

def test_home_uses_new_mobile_material_shell(client):
    response = client.get("/", environ_base={"REMOTE_ADDR": "127.0.0.1"})

    assert response.status_code == 200
    assert b"New download" in response.data
    assert b"data-theme" in response.data
    assert b"viewport" in response.data


def test_queue_request_persists_job_and_returns_id(client):
    response = client.post(
        "/api/jobs",
        json={"url": "https://www.youtube.com/watch?v=video123", "quality": "1080"},
        environ_base={"REMOTE_ADDR": "127.0.0.1"},
    )

    assert response.status_code == 202
    job_id = response.json["jobs"][0]["id"]
    assert job_id
    assert response.json["jobs"][0]["status"] == "queued"

    listing = client.get("/api/jobs", environ_base={"REMOTE_ADDR": "127.0.0.1"})
    assert listing.status_code == 200
    assert listing.json["total"] == 1
    assert listing.json["items"][0]["id"] == job_id


def test_cidr_allowlist_covers_health_and_api(client):
    response = client.get("/healthz", environ_base={"REMOTE_ADDR": "192.0.2.8"})

    assert response.status_code == 403
def test_batch_queue_does_not_partially_create_jobs_when_queue_is_full(client):
    manager = client.application.extensions["ytpi_manager"]
    manager.settings = replace(manager.settings, queue_limit=1)

    response = client.post(
        "/api/jobs",
        json={"urls": ["https://youtu.be/one", "https://youtu.be/two"]},
        environ_base={"REMOTE_ADDR": "127.0.0.1"},
    )

    assert response.status_code == 429
    listing = client.get("/api/jobs", environ_base={"REMOTE_ADDR": "127.0.0.1"})
    assert listing.json["total"] == 0
