# yt-transcript

Turn a YouTube video into readable notes in one run: metadata, a summary
section, chapters, and the transcript formatted into paragraphs with a
timestamp on each (every timestamp links to that moment in the video).
Optionally also an HTML page, plain text, JSON, and screenshots captured at
the moments that matter.

Works on Windows, macOS, Linux, and WSL.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate        # Linux / WSL / macOS
# .\.venv\Scripts\Activate.ps1   # PowerShell
pip install -r requirements.txt

python yt_transcript.py "https://www.youtube.com/watch?v=VIDEO_ID"          # Markdown notes
python yt_transcript.py "https://www.youtube.com/watch?v=VIDEO_ID" --all    # + HTML, txt, JSON, screenshots
```

Or let the launcher handle the venv: `python .claude/skills/yt-transcript/scripts/run.py <url> [flags]`.

> **Why a pinned venv, not `uv run`:** newer `youtube-transcript-api` releases trip YouTube's bot-block on residential IPs far more often. `requirements.txt` pins a version that works; `uv run` would pull the latest every time.

## What you get

`Notes/<Video title>.md`, plus with options:

| File | Option |
|---|---|
| `<title>.html` — search box, screenshot gallery with lightbox, chapter links, dark mode, print styles | `--html` (`--self-contained` embeds the images) |
| `<title>.txt` | `--txt` |
| `<title>.json` — metadata, raw caption segments, paragraphs, screenshots | `--json` |
| `<title>_files/shot_MM-SS.jpg` — screenshots, also shown inline in the transcript | `-s` / `--screenshots` |

`--all` turns all of them on.

### Where notes are saved

1. `-d DIR` if given.
2. Otherwise `<project>/Notes`, where `<project>` is the git root of `--base-dir`
   (default: the current folder), or that folder itself if it is not in a repo.
   An existing `notes` folder is reused whatever its case.
3. With no usable folder (home, a drive root, temp), this project's own `Notes/`.

### Summary

The script writes an extractive summary (the most content-dense sentences,
with timestamps) between `<!-- yt-summary:start -->` markers. Swap in a
written one any time, offline, across every format at once:

```bash
python add_summary.py "Notes/My Video.md" summary.md
```

Re-running on the same video keeps a written summary. `--summary-file FILE`
uses one from the start.

### Screenshots

`-s auto` (the default mode) scores candidate moments from four signals and
merges those that land within 6 seconds of each other, so agreeing signals win:

| Signal | Why it matters |
|---|---|
| Chapter starts | The creator's own map of the video |
| Speaker cues — "as you can see", "this slide", "right here", "let me show you" | The speaker is pointing at something on screen |
| Scene changes (ffmpeg, keyframes only, fast) | A new slide, a new window, a cut |
| "Most replayed" peaks | What viewers rewatched |

The best picks are grabbed from a ≤720p video-only download (deleted afterwards
unless `--keep-video`), then near-duplicates are dropped with a 256-bit
perceptual hash. Chapter frames survive unless practically identical. Use one
signal alone with `-s chapters|cues|scenes|heatmap`, add exact moments with
`--shot-times 1:30 4:05`, or a regular cadence with `--shot-interval 30`.

ffmpeg comes from `PATH` or, failing that, the static binary bundled with
`imageio-ffmpeg`. yt-dlp needs a JavaScript runtime (Node, Deno, or Bun) on
`PATH` to pass YouTube's player challenge; without one, screenshots are
skipped and everything else is still written.

## Options

```
yt_transcript.py <url-or-id> [options]
```

| Flag | Description |
|---|---|
| `-o`, `--output NAME` | Base filename (default: the video title, hashtags removed) |
| `-d`, `--directory DIR` | Exact output folder |
| `--base-dir DIR` | Working folder used to find the project's `Notes/` (default: current folder) |
| `--html`, `--txt`, `--json`, `--all` | Extra outputs (Markdown is always written) |
| `--self-contained` | Embed screenshots in the HTML |
| `-l`, `--lang L [L...]` | Preferred caption languages |
| `--raw` | One caption line per line, no reformatting |
| `--no-timestamps` | No per-paragraph timestamps |
| `-m`, `--reformat-model light\|full` | `full` restores punctuation with an ML model |
| `-p`, `--paragraph-sentences N` | Max sentences per paragraph (default 4) |
| `--summary-file FILE`, `--summary-sentences N` | Written summary; size of the extractive one |
| `-s`, `--screenshots [MODE]` | `auto`, `chapters`, `cues`, `scenes`, `heatmap` |
| `--shot-times T...`, `--shot-interval S`, `--max-shots N` | Extra / regular / capped screenshots |
| `--shot-height H`, `--keep-video` | Download resolution (default 720); keep the video |
| `--refresh` | Ignore the cache and refetch |
| `-q`, `-v` | Quieter / debug output |

`-t` and `-r` from 0.1 still parse; timestamps and formatting are now the default.

### Cache and logs

Metadata and captions are cached per video (and language) so re-runs never
refetch: `%LOCALAPPDATA%\yt-transcript` on Windows, `~/Library/Caches/yt-transcript`
on macOS, `$XDG_CACHE_HOME/yt-transcript` (or `~/.cache/yt-transcript`) on
Linux. Override with `YT_TRANSCRIPT_CACHE`. Warnings and errors also go to
`yt-transcript.log` there.

## Claude Code integration

The repo ships a skill at `.claude/skills/yt-transcript/` and a `/yt-transcript`
command. Paste a YouTube URL in chat, or run `/yt-transcript <url> [flags]`.
Claude runs the launcher once, reads the transcript, writes a summary, and
puts it in with `run.py add-summary`.

`scripts/run.py` is the launcher on every OS (`run.ps1` and `run.sh` just call
it). It does not change directory, so notes land in the caller's project. It
finds this checkout via `YT_TRANSCRIPT_PROJECT`, its own location, or common
clone paths (cloning to `~/code/yt-transcript` as a last resort), uses a per-OS
venv (`.venv_windows`, `.venv_mac`, `.venv_linux`, or `.venv`), and reinstalls
requirements only when `requirements.txt` changes.

## Tests

```bash
pip install -r requirements-dev.txt
python -m pytest -q
```

## License

MIT
