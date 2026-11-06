---
description: Turn a YouTube video into notes (summary, chapters, timestamped transcript; optional HTML and screenshots) in this project's Notes folder
argument-hint: <youtube-url-or-video-id> [--all | --html | -s | other flags]
---

Invoke the `yt-transcript` skill for: $ARGUMENTS

Follow the skill: run `scripts/run.py` once with the URL and any flags the user gave (`--all`, `--html`, `-s`, `-l <code>`, `-o <name>`, ...), passing `--base-dir` set to the current working folder, then write the summary and put it in with `run.py add-summary`. If no URL or video ID was given, ask for one before running.
