from pathlib import Path
import os
import subprocess


def test_entrypoint_recursively_assigns_sqlite_volume_to_app_user(tmp_path):
    calls = tmp_path / "calls.log"
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for command in ("mkdir", "chown", "gosu"):
        stub = bin_dir / command
        stub.write_text("#!/bin/sh\nprintf '%s\\n' \"" + command + " $*\" >> \"$CALLS_LOG\"\n")
        stub.chmod(0o755)
    env = os.environ | {"PATH": f"{bin_dir}:{os.environ['PATH']}", "CALLS_LOG": str(calls)}

    subprocess.run(["/bin/sh", "docker-entrypoint.sh", "waitress-serve", "app:app"],
                   check=True, env=env, capture_output=True, text=True)
    commands = calls.read_text().splitlines()

    assert "chown -R appuser:appuser /app/data" in commands
    assert "chown appuser:appuser /app/downloads" in commands
    assert commands[-1] == "gosu appuser waitress-serve app:app"
