#!/usr/bin/env python3
"""Cross-platform launcher for the yt-transcript skill (Windows, macOS, Linux, WSL).

    python run.py <url-or-id> [yt_transcript options]      # Windows
    python3 run.py <url-or-id> [yt_transcript options]     # macOS / Linux / WSL
    python run.py add-summary <notes.md> <summary.md|->    # swap in a written summary

It does not change directory, so notes land under the caller's working folder.

Finding the yt-transcript project, first match wins:
  1. $YT_TRANSCRIPT_PROJECT
  2. this file's own repo (when the skill lives in <repo>/.claude/skills/...)
  3. the usual clone locations (see CANDIDATES)
  4. a fresh clone of $YT_TRANSCRIPT_REPO into ~/code/yt-transcript

Venv per OS (so WSL and Windows can share one checkout): .venv_windows,
.venv_mac, or .venv_linux, else .venv; created on first run. Requirements are
reinstalled only when requirements.txt changes (hash stamp in the venv).
"""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO_URL = os.environ.get("YT_TRANSCRIPT_REPO", "https://github.com/lelandg/yt-transcript.git")
HOME = Path.home()
CANDIDATES = [
    Path(r"D:\Documents\Code\GitHub\yt-transcript"),
    Path("/mnt/d/Documents/Code/GitHub/yt-transcript"),
    HOME / "code" / "GitHub" / "yt-transcript",
    HOME / "code" / "yt-transcript",
    HOME / "Documents" / "Code" / "GitHub" / "yt-transcript",
    HOME / "src" / "yt-transcript",
]
CLONE_TO = HOME / "code" / "yt-transcript"


def say(msg: str) -> None:
    print(f">>> {msg}", file=sys.stderr, flush=True)


def is_project(p: Path) -> bool:
    return (p / "yt_transcript.py").is_file() and (p / "requirements.txt").is_file()


def find_project() -> Path:
    env = os.environ.get("YT_TRANSCRIPT_PROJECT")
    if env:
        p = Path(env).expanduser()
        if is_project(p):
            return p
        say(f"YT_TRANSCRIPT_PROJECT={env} is not a yt-transcript checkout; looking elsewhere")
    here = Path(__file__).resolve()
    for parent in here.parents:
        if is_project(parent):
            return parent
    for c in CANDIDATES:
        try:
            if is_project(c):
                return c
        except OSError:
            continue
    say(f"yt-transcript not found; cloning {REPO_URL} to {CLONE_TO}")
    CLONE_TO.parent.mkdir(parents=True, exist_ok=True)
    if subprocess.run(["git", "clone", "--depth", "1", REPO_URL, str(CLONE_TO)]).returncode != 0:
        sys.exit("ERROR: clone failed. Clone it yourself and set YT_TRANSCRIPT_PROJECT to its folder.")
    return CLONE_TO


def venv_python(venv: Path) -> Path:
    return venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def ensure_venv(project: Path) -> Path:
    tag = {"win32": ".venv_windows", "darwin": ".venv_mac"}.get(sys.platform, ".venv_linux")
    for name in (tag, ".venv"):
        py = venv_python(project / name)
        if py.exists():
            venv = project / name
            break
    else:
        venv = project / tag
        say(f"Creating {venv}")
        if subprocess.run([sys.executable, "-m", "venv", str(venv)]).returncode != 0:
            # A half-built venv (python but no pip) would be reused next time; remove it.
            shutil.rmtree(venv, ignore_errors=True)
            sys.exit(
                f"ERROR: could not create {venv}. On Debian/Ubuntu install python3-venv "
                f"(sudo apt install python3-venv), then run this again."
            )
    py = venv_python(venv)

    req = project / "requirements.txt"
    # Ignore line endings: a Windows checkout (CRLF) and WSL (LF) must agree.
    want = hashlib.sha256(req.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
    stamp = venv / ".ytt-requirements.sha256"
    have = stamp.read_text().strip() if stamp.exists() else ""
    if have != want:
        say(f"Installing requirements into {venv.name}")
        cmd = [str(py), "-m", "pip", "install", "--quiet", "--disable-pip-version-check", "-r", str(req)]
        if subprocess.run(cmd).returncode != 0:
            # No stamp is written, so the next run retries the install.
            sys.exit(
                f"ERROR: installing requirements into {venv} failed (see pip's output above). "
                f"Fix the cause and run again, or delete {venv} to rebuild it."
            )
        stamp.write_text(want)
    return py


def main() -> int:
    args = sys.argv[1:]
    project = find_project()
    py = ensure_venv(project)
    script = "yt_transcript.py"
    if args and args[0] in ("add-summary", "add_summary"):
        script, args = "add_summary.py", args[1:]
    env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
    return subprocess.run([str(py), str(project / script), *args], env=env).returncode


if __name__ == "__main__":
    sys.exit(main())
