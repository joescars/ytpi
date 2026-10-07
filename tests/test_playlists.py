def test_playlist_can_be_edited_then_synced_without_marking_it_successful(client):
    queued = client.post(
        "/api/jobs",
        json={"url": "https://www.youtube.com/playlist?list=PL_TEST_1"},
        environ_base={"REMOTE_ADDR": "127.0.0.1"},
    )
    assert queued.status_code == 202

    playlists = client.get("/api/playlists", environ_base={"REMOTE_ADDR": "127.0.0.1"})
    assert playlists.status_code == 200
    playlist = playlists.json["items"][0]
    assert playlist["name"] == "PL_TEST_1"
    repo = client.application.extensions["ytpi_repository"]
    first_job_id = queued.json["jobs"][0]["id"]
    repo.update_job(first_job_id, status="finished", stage="Finished")
    repo.set_playlist_sync(playlist["id"], "successful", first_job_id, success=True)
    previous_success = repo.get_playlist(playlist["id"])["last_successful_sync_at"]

    edited = client.put(
        f"/api/playlists/{playlist['id']}",
        json={"category": "Documentaries", "quality": "720", "audio_only": False, "audio_format": "mp3"},
        environ_base={"REMOTE_ADDR": "127.0.0.1"},
    )
    assert edited.status_code == 200
    assert client.get("/api/playlists", environ_base={"REMOTE_ADDR": "127.0.0.1"}).json["items"][0]["category"] == "Documentaries"

    sync = client.post(f"/api/playlists/{playlist['id']}/sync", environ_base={"REMOTE_ADDR": "127.0.0.1"})
    assert sync.status_code == 202
    updated = client.get("/api/playlists", environ_base={"REMOTE_ADDR": "127.0.0.1"}).json["items"][0]
    assert updated["sync_status"] == "requested"
    assert updated["last_successful_sync_at"] == previous_success


def test_playlist_settings_reject_path_traversal(client):
    queued = client.post("/api/jobs", json={"url": "https://www.youtube.com/playlist?list=PL_TEST_2"},
                         environ_base={"REMOTE_ADDR": "127.0.0.1"})
    playlist_id = client.get("/api/playlists", environ_base={"REMOTE_ADDR": "127.0.0.1"}).json["items"][0]["id"]
    response = client.put(f"/api/playlists/{playlist_id}", json={"category": "../outside"},
                          environ_base={"REMOTE_ADDR": "127.0.0.1"})
    assert response.status_code == 400
    assert queued.status_code == 202
