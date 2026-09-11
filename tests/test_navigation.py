import pytest
from flask import url_for
from test_app import client, LOCAL


def test_all_pages_have_consistent_navigation(client):
    """Test that all pages have consistent navigation with active state indication."""
    # Test home page
    resp = client.get("/", environ_base={"REMOTE_ADDR": "127.0.0.1"})
    assert resp.status_code == 200
    
    # Check for primary navigation elements
    html = resp.data.decode('utf-8')
    assert "New Download" in html or "Queue Download" in html  # Primary navigation item
    assert "Downloads" in html or "Dashboard" in html  # Downloads/history navigation
    assert "Playlists" in html  # Playlists navigation
    
    # Check for only one h1 per page
    assert html.count("<h1") == 1
    
    # Check for active state on home page
    assert 'aria-current="page"' in html or 'class="active"' in html
    
    # Test dashboard page
    resp = client.get("/status", environ_base={"REMOTE_ADDR": "127.0.0.1"})
    assert resp.status_code == 200
    html = resp.data.decode('utf-8')
    assert html.count("<h1") == 1  # Only one h1
    assert 'aria-current="page"' in html or 'class="active"' in html


def test_navigation_is_touch_friendly(client):
    """Test that navigation is touch-friendly with adequate spacing."""
    resp = client.get("/", environ_base={"REMOTE_ADDR": "127.0.0.1"})
    html = resp.data.decode('utf-8')
    
    # Check for touch-friendly navigation structure
    assert 'nav-link' in html  # Has navigation links
    assert 'min-height:' in html or 'padding:' in html or 'min-width:' in html  # Has sizing styles
    
    # Check navigation is compact (not taking too much space)
    # Should have a responsive design
    assert 'viewport' in html.lower()  # Has viewport meta tag
    
    # Check for touch-friendly button styles
    assert 'btn' in html  # Has button classes


def test_no_duplicate_dashboard_links(client):
    """Test that there are no duplicate Dashboard links in navigation."""
    resp = client.get("/", environ_base={"REMOTE_ADDR": "127.0.0.1"})
    html = resp.data.decode('utf-8')
    
    # Count occurrences of Dashboard/Status links
    dashboard_link_count = html.count('href="/status"')
    # Should have exactly one Dashboard link in navigation
    assert dashboard_link_count == 1