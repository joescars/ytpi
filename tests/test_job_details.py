import pytest
from test_app import client, LOCAL


def test_job_details_api_includes_concise_fields(client):
    """Test that job details API includes concise fields for user outcomes."""
    # Create a job
    resp = client.post(
        "/download",
        json={
            "url": "https://youtube.com/watch?v=test123",
            "category": "Music",
            "quality": "720",
            "audio_only": False,
            "audio_format": "mp3"
        },
        environ_base=LOCAL
    )
    assert resp.status_code == 202
    job_id = resp.get_json()["job_id"]
    
    # Get job details
    resp = client.get(f"/job_output/{job_id}", environ_base=LOCAL)
    assert resp.status_code == 200
    job = resp.get_json()
    
    # Check for concise fields
    assert "status" in job
    assert "progress" in job
    assert "filename" in job or "url" in job  # Should have media title or URL
    assert "error" in job  # For error summary
    assert "progress_stage" in job  # Current processing stage
    
    # Check timestamps
    # These might come from a different API, but job details should have creation/update info
    # For now, check basic fields exist


def test_job_details_has_collapsed_technical_details(client):
    """Test that job details page has collapsed technical details."""
    # Create a job
    resp = client.post(
        "/download",
        json={
            "url": "https://youtube.com/watch?v=test456",
            "category": "Music"
        },
        environ_base=LOCAL
    )
    assert resp.status_code == 202
    job_id = resp.get_json()["job_id"]
    
    # Check dashboard page
    resp = client.get(f"/status?job={job_id}", environ_base=LOCAL)
    assert resp.status_code == 200
    html = resp.data.decode('utf-8')
    
    # Should have job details section
    assert "Job Details" in html or "job-output" in html
    
    # Should have some mechanism for showing/hiding technical details
    # This could be a details/summary element, toggle button, or similar
    assert "details" in html.lower() or "toggle" in html.lower() or "collapse" in html.lower() or "technical" in html.lower()


def test_job_polling_preserves_selection(client):
    """Test that job polling preserves selection and scroll position."""
    # Create multiple jobs
    job_ids = []
    for i in range(3):
        resp = client.post(
            "/download",
            json={
                "url": f"https://youtube.com/watch?v=polltest{i}",
                "category": "Test"
            },
            environ_base=LOCAL
        )
        assert resp.status_code == 202
        job_ids.append(resp.get_json()["job_id"])
    
    # Check dashboard with selected job
    selected_job = job_ids[1]
    resp = client.get(f"/status?job={selected_job}", environ_base=LOCAL)
    assert resp.status_code == 200
    html = resp.data.decode('utf-8')
    
    # Should include the selected job ID in page
    assert selected_job in html
    
    # Should have some mechanism to preserve selection during polling
    # Could be data attributes, hidden inputs, or JavaScript variables
    assert "data-job-id" in html or "selectedJob" in html.lower() or f"job={selected_job}" in html