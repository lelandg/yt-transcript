#!/usr/bin/env bash
# Bash shim for the yt-transcript skill (Linux, macOS, WSL, Git Bash).
# All logic lives in run.py; this only finds a Python and forwards the arguments.
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY="$(command -v python3 || command -v python)"
exec "$PY" "$DIR/run.py" "$@"
