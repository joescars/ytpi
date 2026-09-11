"""Test the playlist sync output parser."""

from ytpi_app.manager import DownloadManager


def test_parse_playlist_sync_output_basic():
    """Test basic parsing of yt-dlp output."""
    output = """
[youtube:tab] Downloading playlist PLtest123 - add --no-playlist to just download video
[download] Downloading playlist: Test Playlist
[youtube:tab] PLtest123: Downloading webpage
[download] Downloading 5 videos
[download] Downloading item 1 of 5
[download] Destination: /downloads/Music/test-video-1.mp4
[download] 100% of   10.00MiB in 00:00:05 at 2.00MiB/s
[download] Downloading item 2 of 5
[download] test-video-2.mp4 has already been downloaded
[download] Downloading item 3 of 5
[youtube] Extracting URL: video3
[download] Destination: /downloads/Music/test-video-3.mp4
[download] 100% of   15.00MiB in 00:00:10 at 1.50MiB/s
[download] Downloading item 4 of 5
[youtube] video4: Downloading webpage
ERROR: [youtube] video4: Unable to download webpage: HTTP Error 404: Not Found
[download] Downloading item 5 of 5
[youtube] Extracting URL: video5
[download] Destination: /downloads/Music/test-video-5.mp4
[download] 100% of    8.00MiB in 00:00:04 at 2.00MiB/s
[download] Finished downloading playlist: Test Playlist
"""
    
    result = DownloadManager._parse_playlist_sync_output(output)
    
    assert result["discovered_count"] == 5
    assert result["downloaded_count"] == 3  # items 1, 3, 5
    assert result["already_present_count"] == 1  # item 2
    assert result["failed_count"] == 1  # item 4
    
    # Check items details
    last_sync_result = result["last_sync_result"]
    assert last_sync_result["discovered"] == 5
    assert last_sync_result["downloaded"] == 3
    assert last_sync_result["already_present"] == 1
    assert last_sync_result["failed"] == 1
    assert len(last_sync_result["items"]) == 5
    
    # Check first item
    item1 = last_sync_result["items"][0]
    assert item1["item"] == 1
    assert item1["status"] == "downloaded"
    assert item1["filename"] == "/downloads/Music/test-video-1.mp4"
    
    # Check second item (already present)
    item2 = last_sync_result["items"][1]
    assert item2["item"] == 2
    assert item2["status"] == "already_present"
    assert item2["filename"] == "test-video-2.mp4"
    
    # Check fourth item (failed)
    item4 = last_sync_result["items"][3]
    assert item4["item"] == 4
    assert item4["status"] == "failed"
    assert "ERROR:" in item4["error"]


def test_parse_playlist_sync_output_no_item_lines():
    """Test parsing when no 'Downloading item X of Y' lines are present."""
    output = """
[download] Downloading playlist: Test Playlist
[download] Downloading 3 videos
[download] Destination: /downloads/video1.mp4
[download] 100% complete
[download] video2.mp4 has already been downloaded
ERROR: Some error occurred
[download] Destination: /downloads/video3.mp4
[download] 100% complete
"""
    
    result = DownloadManager._parse_playlist_sync_output(output)
    
    # Should still get counts from patterns
    assert result["discovered_count"] == 3  # From "Downloading 3 videos"
    assert result["downloaded_count"] == 2  # Two "Destination:" lines
    assert result["already_present_count"] == 1  # One "has already been downloaded"
    assert result["failed_count"] == 1  # One "ERROR:" line
    
    # Items list might be empty
    last_sync_result = result["last_sync_result"]
    assert last_sync_result["discovered"] == 3
    assert last_sync_result["downloaded"] == 2
    assert last_sync_result["already_present"] == 1
    assert last_sync_result["failed"] == 1


def test_parse_playlist_sync_output_empty():
    """Test parsing empty output."""
    result = DownloadManager._parse_playlist_sync_output("")
    
    assert result["discovered_count"] == 0
    assert result["downloaded_count"] == 0
    assert result["already_present_count"] == 0
    assert result["failed_count"] == 0
    
    last_sync_result = result["last_sync_result"]
    assert last_sync_result["discovered"] == 0
    assert last_sync_result["downloaded"] == 0
    assert last_sync_result["already_present"] == 0
    assert last_sync_result["failed"] == 0
    assert last_sync_result["items"] == []


def test_parse_playlist_sync_output_partial():
    """Test parsing partial/incomplete output."""
    output = """
[download] Downloading playlist: My Playlist
[download] Downloading item 1 of 10
[download] Destination: /downloads/video1.mp4
[download] 50% of 10.0MiB
"""
    
    result = DownloadManager._parse_playlist_sync_output(output)
    
    assert result["discovered_count"] == 10  # From "Downloading item 1 of 10"
    assert result["downloaded_count"] == 1  # One "Destination:" line
    assert result["already_present_count"] == 0
    assert result["failed_count"] == 0
    
    # Item 1 should be marked as downloaded
    items = result["last_sync_result"]["items"]
    assert len(items) == 1
    assert items[0]["item"] == 1
    assert items[0]["status"] == "downloaded"
    assert items[0]["filename"] == "/downloads/video1.mp4"