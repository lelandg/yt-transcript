---
name: yt-transcript
description: Download a YouTube video's transcript to this project's Notes directory. Use whenever the user provides a YouTube URL (youtube.com/watch, youtu.be, shorts, embed) or a bare 11-character video ID and asks to fetch, save, download, grab, or transcribe the transcript/captions/subtitles — even if they don't explicitly name this skill. Also trigger on phrases like "get the transcript of this video", "save the captions", or "transcribe https://youtu.be/...".
---

# yt-transcript

Downloads a YouTube transcript via the project's own `yt_transcript.py` and saves the output into `./Notes/`.

This is the project-local copy of the skill — the wrappers in `scripts/` resolve the project root relative to their own location, so it just works wherever the repo is cloned.

## When to use

Trigger whenever the user supplies a YouTube URL or a bare 11-character video ID and wants the transcript captured to a file. Accepts any URL form the underlying script supports: full `youtube.com/watch?v=...`, `youtu.be/...`, `/shorts/...`, `/embed/...`, or a raw ID like `dQw4w9WgXcQ`.

## How to run

Use the bundled wrapper. It handles the full venv lifecycle so we don't depend on whatever Python happens to be on PATH or a stale global pip install:

1. cd into the project root
2. Pick a venv: on Linux/WSL prefer `.venv_linux`, on Windows prefer `.venv_windows`; fall back to `.venv`; create the platform-specific one if neither exists
3. Activate it
4. Install `requirements.txt` if `youtube_transcript_api` isn't importable
5. Run `yt_transcript.py` with whatever args we pass

**PowerShell (Windows):**

```powershell
& ".\.claude\skills\yt-transcript\scripts\run.ps1" "<URL_OR_ID>"
```

**Bash (Linux/WSL/macOS):**

```bash
bash ./.claude/skills/yt-transcript/scripts/run.sh "<URL_OR_ID>"
```

The wrapper cwd's into the project root, so the `yt_transcript.py` default output of `./Notes` lands in the right place automatically. Pass `-d <path>` to override.

First run creates the venv and installs deps; subsequent runs skip that and just execute.

**Why a venv (not `uv run`, not global pip):** `uv run` installs the latest `youtube-transcript-api` on every fresh cache, and newer releases trip YouTube's bot-block much more aggressively on the same residential IP. A pinned venv avoids that churn — once the venv has a working version, it keeps working.

## Useful flags

Pass these through when the user asks for the corresponding behavior — don't add them speculatively:

| User intent | Flag |
|---|---|
| Custom filename | `-o <name>` |
| Include `[HH:MM:SS]` timestamps | `-t` |
| Non-English / specific language | `-l <code>` (e.g. `-l es`) |
| Reformat into readable prose | `-r` |
| ML-based punctuation restore | `-r -m full` |
| Sentences per paragraph | `-p <N>` (with `-r`) |

Example with flags:

```powershell
& ".\.claude\skills\yt-transcript\scripts\run.ps1" "<URL>" -t -r
```

## After running

Report the saved file path (the script logs `INFO: Saved to: ...` on the last stdout line). If the user asked to read or summarize it, read the file from `./Notes/` afterward.

## Failure modes

- **IP-blocked by YouTube** — surface the error verbatim; don't retry. If the venv has a newer `youtube-transcript-api` that got blocked, suggest pinning to an older version inside the venv (`pip install 'youtube-transcript-api<1.0'`) or running from a different network.
- **Transcripts disabled on the video** — script exits non-zero with a clear error; surface it and stop.
- **Bare ID not 11 chars** — ask the user to confirm the URL or ID rather than guessing.
- **`-r -m full` missing deps** — tell the user to `pip install "deepmultilingualpunctuation>=1.0" "transformers<5" nltk` *inside the activated venv*, or drop back to `-m light`.
