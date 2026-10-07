#!/bin/sh
set -eu
mkdir -p /app/data /app/downloads
# Bind-mounted database files may retain the host owner's UID even after the
# mount directory is writable. Recursively hand the SQLite database and WAL
# sidecars to appuser before dropping privileges.
chown -R appuser:appuser /app/data
chown appuser:appuser /app/downloads
exec gosu appuser "$@"
