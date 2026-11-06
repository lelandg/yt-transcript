#!/usr/bin/env python3
"""Put a written summary into notes made by yt_transcript.py, without refetching.

Replaces the Summary section of NOTES.md and of any sibling .html / .txt /
.json written by the same run.

Usage:
    python add_summary.py "Notes/My Video.md" summary.md
    python add_summary.py "Notes/My Video.md" - < summary.md
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from ytt.paths import strip_note_suffix
from ytt.summary import inject


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    p.add_argument("notes", help="The .md file yt_transcript.py wrote")
    p.add_argument("summary", help="Markdown summary file, or - for stdin")
    a = p.parse_args(argv)

    given = Path(a.notes)
    md = given.with_name(strip_note_suffix(given.name) + ".md")
    if not md.exists():
        print(f"ERROR: notes file not found: {md}", file=sys.stderr)
        return 1
    if a.summary == "-":
        sys.stdin.reconfigure(encoding="utf-8")
        text = sys.stdin.read()
    else:
        text = Path(a.summary).read_text(encoding="utf-8")
    if not text.strip():
        print("ERROR: summary is empty", file=sys.stderr)
        return 1

    try:
        changed = inject(md, text)
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    js = md.with_suffix(".json")
    if js.exists():
        d = json.loads(js.read_text(encoding="utf-8"))
        d["summary_md"] = text.strip()
        js.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
        changed.append(js)
    for c in changed:
        print(f"Updated summary: {c}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
