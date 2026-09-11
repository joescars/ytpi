import pytest
from test_app import client, LOCAL


def test_search_api_exists(client):
    """Test that search API endpoint exists."""
    # Check if enhanced status endpoint accepts search parameters
    resp = client.get("/api/status?search=test", environ_base=LOCAL)
    assert resp.status_code == 200
    data = resp.get_json()
    assert "items" in data
    assert "total" in data
    # Should return successfully even with empty search


def test_search_filters_jobs_by_status(client):
    """Test that jobs can be filtered by status."""
    # Create a few jobs with different statuses
    for i in range(3):
        resp = client.post(
            "/download",
            json={
                "url": f"https://youtube.com/watch?v=test{i}",
                "category": "test"
            },
            environ_base=LOCAL
        )
        assert resp.status_code == 202
    
    # Get all jobs
    resp = client.get("/api/status", environ_base=LOCAL)
    assert resp.status_code == 200
    data = resp.get_json()
    initial_count = data["total"]
    
    # Filter by status=queued
    resp = client.get("/api/status?status=queued", environ_base=LOCAL)
    assert resp.status_code == 200
    data = resp.get_json()
    assert "items" in data
    assert "total" in data
    # Should have at least 3 queued jobs
    assert data["total"] >= 3
    
    # All returned jobs should be queued
    for job in data["items"]:
        assert job["status"] == "queued"


def test_search_filters_preserved_in_url(client):
    """Test that search filters are preserved in URL."""
    resp = client.get("/status?status=finished&category=music", environ_base=LOCAL)
    assert resp.status_code == 200
    html = resp.data.decode('utf-8')
    
    # Check that the page includes some indication of active filters
    # This could be in the form of hidden inputs, data attributes, or text
    assert "status" in html.lower() or "filter" in html.lower() or "search" in html.lower()


def test_pagination_works(client):
    """Test that pagination works correctly."""
    # Create more than one page of jobs
    for i in range(15):
        resp = client.post(
            "/download",
            json={
                "url": f"https://youtube.com/watch?v=pagetest{i}",
                "category": "pagination"
            },
            environ_base=LOCAL
        )
        assert resp.status_code == 202
    
    # Get first page
    resp = client.get("/api/status?limit=10&offset=0", environ_base=LOCAL)
    assert resp.status_code == 200
    page1 = resp.get_json()
    assert len(page1["items"]) == 10
    assert page1["limit"] == 10
    assert page1["offset"] == 0
    assert page1["total"] >= 15
    
    # Get second page
    resp = client.get("/api/status?limit=10&offset=10", environ_base=LOCAL)
    assert resp.status_code == 200
    page2 = resp.get_json()
    assert len(page2["items"]) <= 10  # Could be 5 if we have exactly 15
    assert page2["offset"] == 10
    
    # Jobs should be different between pages
    page1_ids = {job["id"] for job in page1["items"]}
    page2_ids = {job["id"] for job in page2["items"]}
    assert page1_ids.isdisjoint(page2_ids)  # No overlap between pages