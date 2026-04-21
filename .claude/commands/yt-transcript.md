---
description: Download a YouTube transcript into this project's Notes directory
argument-hint: <youtube-url-or-video-id> [extra flags]
---

Invoke the `yt-transcript` skill to download the transcript for: $ARGUMENTS

Use the bundled wrapper at `./.claude/skills/yt-transcript/scripts/run.ps1` (PowerShell) or `./.claude/skills/yt-transcript/scripts/run.sh` (Bash). Pass through any extra flags the user included (`-t`, `-r`, `-l <code>`, `-o <name>`, etc.). If no argument was provided, ask the user for a URL or video ID before running.
