import ipaddress
import json
import shlex
import shutil
import subprocess

import pytest

from ytpi_app.config import Settings
from ytpi_app.manager import DownloadManager
from ytpi_app.repository import JobRepository


@pytest.mark.parametrize("extension", ["mp4", "mp3", "mkv"], ids=["video", "audio", "matroska"])
def test_embed_thumbnail_adds_cover_art_and_keeps_jpeg_sidecar(tmp_path, extension):
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    if not ffmpeg or not ffprobe:
        pytest.skip("ffmpeg and ffprobe are required for thumbnail integration test")

    media_path = tmp_path / f"Music Video.{extension}"
    thumbnail_path = tmp_path / "Music Video-thumb.jpg"
    if extension == "mp4":
        subprocess.run([ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i",
                        "color=c=blue:s=64x64:d=1", "-an", "-c:v", "mpeg4", str(media_path)], check=True)
    elif extension == "mkv":
        subprocess.run([ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i",
                        "color=c=blue:s=64x64:d=1", "-an", "-c:v", "mpeg4", str(media_path)], check=True)
    else:
        subprocess.run([ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i",
                        "sine=frequency=1000:duration=1", "-c:a", "libmp3lame", str(media_path)], check=True)
    subprocess.run([ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i",
                    "color=c=red:s=64x64", "-frames:v", "1", str(thumbnail_path)], check=True)
    settings = Settings(
        host="127.0.0.1", port=7434, db_path=tmp_path / "jobs.db", downloads_dir=tmp_path,
        allowed_cidrs=(ipaddress.ip_network("127.0.0.1/32"),), trust_proxy=False,
        workers=0, queue_limit=10, timeout_seconds=30, max_retries=0,
        max_output_chars=8000, job_retention_hours=168, max_history_jobs=2000,
        yt_dlp="yt-dlp", ffmpeg_path=ffmpeg, enable_remote_components=False, block_private_urls=False,
    )
    manager = DownloadManager(settings, JobRepository(settings.db_path))

    assert manager._embed_thumbnail(media_path) == f"Embedded thumbnail in Music Video.{extension}; kept Music Video-thumb.jpg."
    probe = subprocess.run([ffprobe, "-v", "error", "-show_entries", "stream=codec_type:stream_disposition=attached_pic:stream_tags=mimetype,filename",
                            "-of", "json", str(media_path)], capture_output=True, text=True, check=True)
    streams = json.loads(probe.stdout)["streams"]
    if extension == "mkv":
        assert any(stream.get("tags", {}).get("mimetype") == "image/jpeg" for stream in streams)
    else:
        assert any(stream["disposition"].get("attached_pic") == 1 for stream in streams)
    assert thumbnail_path.is_file()


def test_unsupported_webm_keeps_thumbnail_sidecar_without_embedding(tmp_path):
    media_path = tmp_path / "Music Video.webm"
    thumbnail_path = tmp_path / "Music Video-thumb.jpg"
    media_path.write_bytes(b"webm video fixture")
    thumbnail_path.write_bytes(b"jpeg fixture")
    settings = Settings(
        host="127.0.0.1", port=7434, db_path=tmp_path / "jobs.db", downloads_dir=tmp_path,
        allowed_cidrs=(ipaddress.ip_network("127.0.0.1/32"),), trust_proxy=False,
        workers=0, queue_limit=10, timeout_seconds=30, max_retries=0,
        max_output_chars=8000, job_retention_hours=168, max_history_jobs=2000,
        yt_dlp="yt-dlp", ffmpeg_path="", enable_remote_components=False, block_private_urls=False,
    )
    manager = DownloadManager(settings, JobRepository(settings.db_path))

    assert manager._embed_thumbnail(media_path) is None
    assert media_path.read_bytes() == b"webm video fixture"
    assert thumbnail_path.is_file()


@pytest.mark.parametrize("audio_only", [False, True], ids=["video", "audio"])
def test_download_command_enables_progress_thumbnail_sidecar_and_embedding(tmp_path, audio_only):
    fake_yt_dlp = tmp_path / "fake-yt-dlp"
    fake_yt_dlp.write_text("""#!/bin/sh
printf 'ARGS: %s\\n' "$*"
printf '%s\\n' '[download]   43.0% of   12MiB at  1MiB/s ETA 00:10' '__YTPI_TITLE__A Great Video' '__YTPI_FILEPATH__%(media_path)s'
""".replace("%(media_path)s", str(tmp_path / "downloads" / ("A Great Video.mp3" if audio_only else "A Great Video.mp4"))))
    fake_yt_dlp.chmod(0o755)
    settings = Settings(
        host="127.0.0.1", port=7434, db_path=tmp_path / "jobs.db", downloads_dir=tmp_path / "downloads",
        allowed_cidrs=(ipaddress.ip_network("127.0.0.1/32"),), trust_proxy=False,
        workers=0, queue_limit=10, timeout_seconds=30, max_retries=0,
        max_output_chars=8000, job_retention_hours=168, max_history_jobs=2000,
        yt_dlp=str(fake_yt_dlp), ffmpeg_path="", enable_remote_components=False, block_private_urls=False,
    )
    repository = JobRepository(settings.db_path)
    manager = DownloadManager(settings, repository)
    job = manager.enqueue("https://youtu.be/example", "", "1080", audio_only, "mp3")

    manager._run(job)
    completed = repository.get_job(job["id"])

    assert "--progress" in completed["output"]
    assert "--write-thumbnail" in completed["output"]
    assert "--convert-thumbnails jpg" in completed["output"]
    assert f"thumbnail:{tmp_path / 'downloads'}/%(title)s-thumb.%(ext)s" in completed["output"]
    assert f"--print after_move:__YTPI_FILEPATH__%(filepath)s" in completed["output"]
    assert completed["filename"].endswith("A Great Video.mp3" if audio_only else "A Great Video.mp4")
    assert "43.0%" in completed["output"]
    assert completed["speed"] == "1MiB/s"
    assert completed["eta"] == "00:10"
    repository.close()


def test_manager_download_embeds_thumbnail_and_keeps_sidecar(tmp_path):
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    if not ffmpeg or not ffprobe:
        pytest.skip("ffmpeg and ffprobe are required for thumbnail integration test")

    downloads_dir = tmp_path / "downloads"
    media_path = downloads_dir / "A Great Video.mp4"
    thumbnail_path = downloads_dir / "A Great Video-thumb.jpg"
    fake_yt_dlp = tmp_path / "fake-yt-dlp"
    fake_yt_dlp.write_text("""#!/bin/sh
printf 'ARGS: %s\\n' "$*"
mkdir -p "$(dirname "%(media)s")"
%(create_media)s
%(create_thumbnail)s
printf '%%s\\n' '__YTPI_TITLE__A Great Video' '__YTPI_FILEPATH__%(media)s'
""" % {
        "media": media_path,
        "create_media": shlex.join([ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i",
                                     "color=c=blue:s=64x64:d=1", "-an", "-c:v", "mpeg4", str(media_path)]),
        "create_thumbnail": shlex.join([ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i",
                                         "color=c=red:s=64x64", "-frames:v", "1", str(thumbnail_path)]),
    })
    fake_yt_dlp.chmod(0o755)
    settings = Settings(
        host="127.0.0.1", port=7434, db_path=tmp_path / "jobs.db", downloads_dir=downloads_dir,
        allowed_cidrs=(ipaddress.ip_network("127.0.0.1/32"),), trust_proxy=False,
        workers=0, queue_limit=10, timeout_seconds=30, max_retries=0,
        max_output_chars=8000, job_retention_hours=168, max_history_jobs=2000,
        yt_dlp=str(fake_yt_dlp), ffmpeg_path=ffmpeg, enable_remote_components=False, block_private_urls=False,
    )
    repository = JobRepository(settings.db_path)
    manager = DownloadManager(settings, repository)
    job = manager.enqueue("https://youtu.be/example", "", "1080", False, "mp3")

    manager._run(job)
    completed = repository.get_job(job["id"])

    assert completed["status"] == "finished"
    assert completed["filename"] == str(media_path)
    assert thumbnail_path.is_file()
    probe = subprocess.run([ffprobe, "-v", "error", "-show_entries", "stream=codec_type:stream_disposition=attached_pic",
                            "-of", "json", str(media_path)], capture_output=True, text=True, check=True)
    assert any(stream["disposition"].get("attached_pic") == 1 for stream in json.loads(probe.stdout)["streams"])
    assert "Embedded thumbnail in A Great Video.mp4" in completed["output"]
    repository.close()


def test_manager_persists_title_and_completes_a_download(tmp_path):
    fake_yt_dlp = tmp_path / "fake-yt-dlp"
    fake_yt_dlp.write_text(
        "#!/bin/sh\nprintf '%s\\n' '[download] 43.0% of 12MiB at 1MiB/s ETA 00:10' '[download] Destination: /media/A Great Video.webm' '[Merger] Merging formats into \\\"/media/A Great Video.mp4\\\"' '__YTPI_TITLE__A Great Video'\n"
    )
    fake_yt_dlp.chmod(0o755)
    settings = Settings(
        host="127.0.0.1", port=7434, db_path=tmp_path / "jobs.db", downloads_dir=tmp_path / "downloads",
        allowed_cidrs=(ipaddress.ip_network("127.0.0.1/32"),), trust_proxy=False,
        workers=0, queue_limit=10, timeout_seconds=30, max_retries=0,
        max_output_chars=8000, job_retention_hours=168, max_history_jobs=2000,
        yt_dlp=str(fake_yt_dlp), ffmpeg_path="", enable_remote_components=False, block_private_urls=False,
    )
    repository = JobRepository(settings.db_path)
    manager = DownloadManager(settings, repository)
    job = manager.enqueue("https://youtu.be/example", "", "1080", False, "mp3")

    manager._run(job)
    completed = repository.get_job(job["id"])

    assert completed["status"] == "finished"
    assert completed["title"] == "A Great Video"
    assert completed["progress"] == 100
    assert completed["filename"] == "/media/A Great Video.webm"
    assert "43.0%" in completed["output"]
    repository.close()


def test_failed_download_retries_once_then_succeeds(tmp_path):
    fake_yt_dlp = tmp_path / "fake-yt-dlp"
    fake_yt_dlp.write_text("#!/bin/sh\necho 'temporary network error'\nexit 1\n")
    fake_yt_dlp.chmod(0o755)
    settings = Settings(
        host="127.0.0.1", port=7434, db_path=tmp_path / "retry.db", downloads_dir=tmp_path / "downloads",
        allowed_cidrs=(ipaddress.ip_network("127.0.0.1/32"),), trust_proxy=False,
        workers=0, queue_limit=10, timeout_seconds=30, max_retries=1,
        max_output_chars=8000, job_retention_hours=168, max_history_jobs=2000,
        yt_dlp=str(fake_yt_dlp), ffmpeg_path="", enable_remote_components=False, block_private_urls=False,
    )
    repository = JobRepository(settings.db_path)
    manager = DownloadManager(settings, repository)
    job = manager.enqueue("https://youtu.be/retry", "", "max", False, "mp3")

    manager._run(job)
    retrying = repository.get_job(job["id"])
    assert retrying["status"] == "queued"
    assert retrying["attempt_count"] == 1
    assert "Retrying (1/1)" in retrying["error"]

    fake_yt_dlp.write_text("#!/bin/sh\nprintf '%s\\n' '__YTPI_TITLE__Recovered title'\n")
    manager._run(retrying)
    completed = repository.get_job(job["id"])
    assert completed["status"] == "finished"
    assert completed["attempt_count"] == 2
    assert completed["title"] == "Recovered title"
    repository.close()


def test_successful_download_records_finalized_filename_from_merger_output(tmp_path):
    fake_yt_dlp = tmp_path / "fake-yt-dlp"
    fake_yt_dlp.write_text(
        "#!/bin/sh\nprintf '%s\\n' '[download] Destination: /media/Final Video.f137.mp4' '[Merger] Merging formats into \"/media/Final Video.mp4\"' '__YTPI_TITLE__Final Video'\n"
    )
    fake_yt_dlp.chmod(0o755)
    settings = Settings(
        host="127.0.0.1", port=7434, db_path=tmp_path / "finalized.db", downloads_dir=tmp_path / "downloads",
        allowed_cidrs=(ipaddress.ip_network("127.0.0.1/32"),), trust_proxy=False,
        workers=0, queue_limit=10, timeout_seconds=30, max_retries=0,
        max_output_chars=8000, job_retention_hours=168, max_history_jobs=2000,
        yt_dlp=str(fake_yt_dlp), ffmpeg_path="", enable_remote_components=False, block_private_urls=False,
    )
    repository = JobRepository(settings.db_path)
    manager = DownloadManager(settings, repository)
    job = manager.enqueue("https://youtu.be/finalized", "", "1080", False, "mp3")

    manager._run(job)
    finished = repository.get_job(job["id"])

    assert finished["status"] == "finished"
    assert finished["filename"] == "/media/Final Video.mp4"
    repository.close()
