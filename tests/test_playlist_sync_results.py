"""Tests for playlist sync results (recommendation 8)."""

import json
import time
import tempfile
from pathlib import Path

from ytpi_app.repository import JobRepository
from ytpi_app.manager import DownloadManager


def test_playlist_sync_results_storage():
    """Test repository method for storing sync results."""
    db_path = Path(tempfile.mktemp(suffix='.db'))
    repo = JobRepository(db_path)
    
    try:
        # Create a playlist
        playlist = repo.upsert_playlist(
            url="https://youtube.com/playlist?list=PLtest123",
            name="Test Playlist",
            category="Music",
            quality="best"
        )
        
        # Update with sync results
        repo.update_playlist_sync_results(
            playlist["id"],
            discovered_count=5,
            downloaded_count=3,
            already_present_count=1,
            failed_count=1
        )
        
        # Fetch and verify
        updated_playlist = repo.get_playlist(playlist["id"])
        assert updated_playlist is not None
        
        assert updated_playlist["discovered_count"] == 5
        assert updated_playlist["downloaded_count"] == 3
        assert updated_playlist["already_present_count"] == 1
        assert updated_playlist["failed_count"] == 1
        
        # Verify JSON result
        if updated_playlist.get("last_sync_result"):
            result_json = json.loads(updated_playlist["last_sync_result"])
            assert result_json["discovered"] == 5
            assert result_json["downloaded"] == 3
    finally:
        db_path.unlink(missing_ok=True)


def test_playlist_sync_results_incremental():
    """Test that sync results accumulate correctly."""
    db_path = Path(tempfile.mktemp(suffix='.db'))
    repo = JobRepository(db_path)
    
    try:
        playlist = repo.upsert_playlist(
            url="https://youtube.com/playlist?list=PLtest456",
            name="Test Playlist 2",
            category="Videos",
            quality="720p"
        )
        
        # First sync: 10 items, 5 downloaded, 5 existing
        repo.update_playlist_sync_results(
            playlist["id"],
            discovered_count=10,
            downloaded_count=5,
            already_present_count=5,
            failed_count=0
        )
        
        # Second sync: 8 items, 3 downloaded, 4 existing, 1 failed
        repo.update_playlist_sync_results(
            playlist["id"],
            discovered_count=8,
            downloaded_count=3,
            already_present_count=4,
            failed_count=1
        )
        
        # Should show latest results
        updated = repo.get_playlist(playlist["id"])
        assert updated is not None
        
        assert updated["discovered_count"] == 8
        assert updated["downloaded_count"] == 3
        assert updated["already_present_count"] == 4
        assert updated["failed_count"] == 1
    finally:
        db_path.unlink(missing_ok=True)


def test_playlist_sync_results_with_empty():
    """Test sync results with empty/zero values."""
    db_path = Path(tempfile.mktemp(suffix='.db'))
    repo = JobRepository(db_path)
    
    try:
        playlist = repo.upsert_playlist(
            url="https://youtube.com/playlist?list=PLtest789",
            name="Test Playlist 3",
            category="Audio",
            quality="best",
            audio_only=True,
            audio_format="mp3"
        )
        
        # Update with zero results
        repo.update_playlist_sync_results(
            playlist["id"],
            discovered_count=0,
            downloaded_count=0,
            already_present_count=0,
            failed_count=0
        )
        
        updated = repo.get_playlist(playlist["id"])
        assert updated is not None
        
        assert updated["discovered_count"] == 0
        assert updated["downloaded_count"] == 0
        assert updated["already_present_count"] == 0
        assert updated["failed_count"] == 0
    finally:
        db_path.unlink(missing_ok=True)


def test_playlist_sync_parser_integration():
    """Test that parser output integrates with repository."""
    from ytpi_app.manager import DownloadManager
    
    # Sample yt-dlp output
    output = """
[youtube:tab] Downloading playlist PLtest123
[download] Downloading 3 videos
[download] Downloading item 1 of 3
[download] Destination: /downloads/test1.mp4
[download] Downloading item 2 of 3
[download] test2.mp4 has already been downloaded
[download] Downloading item 3 of 3
[download] Destination: /downloads/test3.mp4
"""
    
    result = DownloadManager._parse_playlist_sync_output(output)
    
    assert result["discovered_count"] == 3
    assert result["downloaded_count"] == 2
    assert result["already_present_count"] == 1
    assert result["failed_count"] == 0
    
    # Verify the result structure can be stored
    last_sync_result = result["last_sync_result"]
    assert last_sync_result["discovered"] == 3
    assert last_sync_result["downloaded"] == 2
    assert last_sync_result["already_present"] == 1
    assert last_sync_result["failed"] == 0