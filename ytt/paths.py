"""Decide where notes go and what they are called."""

from __future__ import annotations

import os
import re
import tempfile
from pathlib import Path

# Only version-control roots: umbrella folders (e.g. a "GitHub" folder holding
# many repos) often carry stray package.json / AGENTS.md files.
PROJECT_MARKERS = (".git", ".hg")

# This repo: the last-resort home for notes when the caller has no folder.
TOOL_HOME = Path(__file__).resolve().parent.parent


def _is_unusable_base(p: Path) -> bool:
    """Home, a filesystem root, or the temp dir."""
    try:
        p = p.resolve()
    except OSError:
        return True
    if p == Path(p.anchor) or p == Path.home().resolve():
        return True
    try:
        if p == Path(tempfile.gettempdir()).resolve():
            return True
    except OSError:
        pass
    return False


def project_root(start: Path) -> Path | None:
    """Nearest ancestor (or self) that looks like a project; stops at home."""
    home = Path.home().resolve()
    p = start.resolve()
    for cand in (p, *p.parents):
        if cand == home or cand == Path(cand.anchor):
            break
        if any((cand / m).exists() for m in PROJECT_MARKERS):
            return cand
    return None


def _notes_dir_in(base: Path) -> Path:
    """Reuse an existing notes folder whatever its case ("notes", "Notes")."""
    try:
        for child in base.iterdir():
            if child.is_dir() and child.name.lower() == "notes":
                return child
    except OSError:
        pass
    return base / "Notes"


def resolve_output_dir(directory: str | None, base_dir: str | None) -> tuple[Path, str]:
    """Return (output dir, why). Priority:

    1. -d/--directory, used as given
    2. --base-dir (the agent's working folder) or the current directory:
       its project root if it is inside one, else the folder itself, + /Notes
    3. this tool's own Notes folder, when there is no usable working folder
    """
    if directory:
        return Path(directory).expanduser().resolve(), "--directory"
    start = Path(base_dir).expanduser() if base_dir else Path(os.getcwd())
    if start.is_dir() and not _is_unusable_base(start):
        root = project_root(start)
        if root is not None:
            return _notes_dir_in(root), f"project root {root}"
        return _notes_dir_in(start.resolve()), f"working folder {start.resolve()}"
    return _notes_dir_in(TOOL_HOME), "no working folder; using the yt-transcript project"


NOTE_SUFFIXES = (".md", ".html", ".txt", ".json")


def strip_note_suffix(name: str) -> str:
    """Drop .md/.html/.txt/.json only, so "Talk v2.0" keeps its ".0"."""
    for suf in NOTE_SUFFIXES:
        if name.lower().endswith(suf):
            return name[: -len(suf)]
    return name


def sanitize_filename(name: str, max_len: int = 120) -> str:
    """Safe on Windows, macOS, and Linux; strips trailing hashtags YouTube titles carry."""
    name = re.sub(r"(\s+#[\w-]+)+\s*$", "", name)  # "Title #tag #tag2" -> "Title"
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", name)
    name = re.sub(r"\s+", " ", name).strip().strip(". ")
    if len(name) > max_len:
        name = name[:max_len].rsplit(" ", 1)[0].strip(". ")
    if name.split(".")[0].upper() in {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}:
        name += "_"
    return name or "transcript"
