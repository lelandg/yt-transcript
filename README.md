# yt-transcript

Download YouTube video transcripts and save them as text files. Optionally reformat raw transcript text into readable, capitalized prose with paragraph breaks.

## Quick Start

```bash
# With uv (recommended — zero setup)
uv run yt_transcript.py "https://www.youtube.com/watch?v=VIDEO_ID"

# With pip
pip install -r requirements.txt
python yt_transcript.py "https://www.youtube.com/watch?v=VIDEO_ID"
```

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
uv run yt_transcript.py "https://youtu.be/dQw4w9WgXcQ"

# Custom output filename
uv run yt_transcript.py "https://youtu.be/dQw4w9WgXcQ" -o my_notes.txt

# Include timestamps
uv run yt_transcript.py "https://youtu.be/dQw4w9WgXcQ" -t

# Reformat into readable prose
uv run yt_transcript.py "https://youtu.be/dQw4w9WgXcQ" -r

# Full ML-based reformatting (requires extra deps)
uv run yt_transcript.py "https://youtu.be/dQw4w9WgXcQ" -r -m full

# Spanish transcript
uv run yt_transcript.py "https://youtu.be/dQw4w9WgXcQ" -l es
```

## Requirements

- Python 3.10+
- `youtube-transcript-api` (installed automatically with `uv run`)

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
