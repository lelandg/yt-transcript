# yt-transcript

Download YouTube video transcripts and save them as text files. Optionally reformat raw transcript text into readable, capitalized prose with paragraph breaks.

## Quick Start

```bash
# Create a venv and install deps (one-time)
python -m venv .venv
source .venv/bin/activate        # Linux/WSL/macOS
# .\.venv\Scripts\Activate.ps1   # PowerShell
pip install -r requirements.txt

# Run
python yt_transcript.py "https://www.youtube.com/watch?v=VIDEO_ID"
```

> **Note on `uv run`:** `uv run yt_transcript.py ...` also works, but it installs the *latest* `youtube-transcript-api` into a fresh cache each time. Newer releases of that library trip YouTube's bot-block on residential IPs noticeably more often than the pinned version in `requirements.txt`. If you hit `RequestBlocked` / `IpBlocked` errors with `uv`, switch to a plain venv as shown above.

## Features

- Extracts transcripts from any YouTube URL format (full URL, short URL, embed, shorts, bare ID)
- Auto-names output files from the video title
- Optional timestamp inclusion
- Language selection for multilingual transcripts
- Light reformatter: splits run-on transcript text into capitalized sentences and paragraphs using only the stdlib
- Full reformatter: uses [deepmultilingualpunctuation](https://github.com/oliverguhr/deepmultilingualpunctuation) for ML-based punctuation restoration

## Usage

```
yt_transcript.py <url> [output_filename] [options]
```

| Flag | Description |
|------|-------------|
| `-o`, `--output` | Override output filename |
| `-d`, `--directory` | Output directory (default: `./Notes`) |
| `-l`, `--lang` | Preferred language(s), e.g. `-l en es` |
| `-t`, `--timestamps` | Include `[HH:MM:SS]` timestamps |
| `-r`, `--reformat` | Post-process into sentences and paragraphs |
| `-m`, `--reformat-model` | `light` (default, stdlib) or `full` (ML model) |
| `-p`, `--paragraph-sentences` | Sentences per paragraph (default: 4) |

### Examples

```bash
# Save transcript with auto-generated filename
python yt_transcript.py "https://www.youtube.com/watch?v=M30gp1315Y4"

# Custom output filename
python yt_transcript.py "https://www.youtube.com/watch?v=M30gp1315Y4" -o my_notes.txt

# Include timestamps
python yt_transcript.py "https://www.youtube.com/watch?v=M30gp1315Y4" -t

# Reformat into readable prose
python yt_transcript.py "https://www.youtube.com/watch?v=M30gp1315Y4" -r

# Full ML-based reformatting (requires extra deps)
python yt_transcript.py "https://www.youtube.com/watch?v=M30gp1315Y4" -r -m full

# Spanish transcript
python yt_transcript.py "https://www.youtube.com/watch?v=M30gp1315Y4" -l es
```

## Claude Code integration

This repo ships a project-local [Claude Code](https://docs.claude.com/claude-code) skill at `.claude/skills/yt-transcript/` and a matching slash command at `.claude/commands/yt-transcript.md`. Open the repo in Claude Code and either:

- Paste a YouTube URL into chat — the skill description triggers it automatically.
- Run `/yt-transcript <url>` — explicit invocation.

The skill uses a bundled wrapper (`scripts/run.ps1` on Windows, `scripts/run.sh` on Linux/WSL/macOS) that:

1. cd's into the project root
2. Picks an existing venv (`.venv_linux` or `.venv_windows` preferred over `.venv`), or creates one
3. Installs `requirements.txt` on first run
4. Runs `yt_transcript.py` with the URL and any extra flags

You can invoke the wrappers directly too — they're portable (they resolve the project root relative to themselves):

```powershell
& ".\.claude\skills\yt-transcript\scripts\run.ps1" "https://www.youtube.com/watch?v=VIDEO_ID" -t
```

```bash
bash ./.claude/skills/yt-transcript/scripts/run.sh "https://www.youtube.com/watch?v=VIDEO_ID" -t
```

## Requirements

- Python 3.10+
- `youtube-transcript-api` (installed via `requirements.txt`)

Optional for `--reformat-model full`:

```bash
pip install "deepmultilingualpunctuation>=1.0" "transformers<5" nltk
```

## Tests

```bash
python -m pytest test_reformat.py -v
```

## License

MIT
