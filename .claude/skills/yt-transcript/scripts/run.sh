#!/usr/bin/env bash
# Linux/WSL runner for the yt-transcript skill.
# Resolves the project root relative to this script's location, so the skill
# is portable — anyone who clones the repo gets a working setup.
#
# Venv lifecycle: prefer .venv_linux > .venv; create .venv_linux if neither
# exists; install requirements.txt if youtube_transcript_api isn't importable.
set -euo pipefail

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
# scripts/ → yt-transcript/ → skills/ → .claude/ → project root
PROJECT="$( cd "$SCRIPT_DIR/../../../.." && pwd )"

cd "$PROJECT"

if [ -d ".venv_linux" ]; then
    VENV=".venv_linux"
elif [ -d ".venv" ]; then
    VENV=".venv"
else
    VENV=".venv_linux"
    echo ">>> No venv found. Creating $PROJECT/$VENV ..."
    python3 -m venv "$VENV"
fi

# shellcheck disable=SC1091
source "$VENV/bin/activate"

if ! python -c "import youtube_transcript_api" 2>/dev/null; then
    echo ">>> Installing requirements into $VENV ..."
    pip install --quiet --upgrade pip
    pip install --quiet -r requirements.txt
fi

# Default output dir is ./Notes (we're cwd'd into the project).
# User-supplied -d will override via argparse last-wins.
exec python yt_transcript.py "$@"
