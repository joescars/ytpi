#!/bin/sh
set -e

# Ensure data and downloads directories exist and are writable by appuser.
# This is necessary when Docker bind-mounts a host directory (e.g. ./data:/app/data)
# that was auto-created by Docker as root before the container user could write to it.
mkdir -p /app/data /app/downloads
chown appuser:appuser /app/data /app/downloads

exec gosu appuser "$@"
