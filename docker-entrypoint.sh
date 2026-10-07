#!/bin/sh
set -eu
mkdir -p /app/data /app/downloads
chown appuser:appuser /app/data /app/downloads
exec gosu appuser "$@"
