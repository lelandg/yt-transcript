---
name: yt-transcript
description: Turn a YouTube video into notes in one run, saved to the current project's Notes folder — summary, chapters, transcript formatted into timestamped paragraphs, and optionally HTML, plain text, JSON, and screenshots of key moments (slides, demos). Use whenever the user gives a YouTube URL (watch, youtu.be, shorts, embed, live) or an 11-character video ID and wants the transcript, captions, subtitles, notes, a summary, or screenshots of it — even if they don't name this skill. Also on "get the transcript of this video", "save the captions", "summarize this video", "grab the slides from this talk".
---

# yt-transcript

One call fetches everything and writes the notes; then you write the summary
into them. Fetches are cached per video, so later runs (new format, more
screenshots) never hit YouTube again unless `--refresh` is passed.

## 1. Run it once

`<skill>` is this skill's base directory (shown when the skill loads).
`<cwd>` is the session's working folder. Use `python` on Windows (PowerShell
tool), `python3` on macOS, Linux, and WSL.

```bash
python3 "<skill>/scripts/run.py" "<URL_OR_ID>" --base-dir "<cwd>" [flags]
```

The launcher finds the yt-transcript project, makes or reuses the per-OS
venv, installs pinned requirements only when they change, and leaves the
working directory alone. First run takes a minute; later runs take seconds.

**Where notes go** (the script decides; don't pass `-d` unless asked):
the git root of `<cwd>` if it is in a repo, else `<cwd>` itself, then
`/Notes` (an existing `notes`/`Notes` folder is reused). With no usable working
folder (home, a drive root, temp), it falls back to the yt-transcript
project's own `Notes`.

**Flags.** Default (no flags) writes the Markdown notes: metadata, summary,
chapters, and the formatted, timestamped transcript. Add only what the user
asks for:

| User wants | Flag |
|---|---|
| Everything (HTML, text, JSON, screenshots) | `--all` |
| A web page (search box, screenshot gallery, dark mode) | `--html` |
| HTML as one portable file, images embedded | `--html --self-contained` |
| Screenshots of key moments | `-s` (same as `-s auto`) |
| Screenshots from chapters / speaker cues / scene changes / replay peaks only | `-s chapters` · `-s cues` · `-s scenes` · `-s heatmap` |
| Frames at specific times | `--shot-times 1:30 4:05` |
| A frame every N seconds | `--shot-interval 30` |
| More or fewer frames | `--max-shots N` (default ≈1 per minute, 6–24) |
| Plain text / data | `--txt` · `--json` |
| Another language | `-l es` (several allowed: `-l de en`) |
| Custom filename | `-o "Name"` |
| No paragraph timestamps / raw caption lines | `--no-timestamps` · `--raw` |
| Better punctuation (ML, ~500 MB model) | `-m full` |
| Refetch, ignoring the cache | `--refresh` |

Old flags `-t` and `-r` are accepted and ignored: timestamps and formatting are now the default.

**How auto screenshots are chosen.** Moments come from four signals, merged
when they land within 6 s of each other so agreeing signals win: chapter
starts; speaker cues ("as you can see", "this slide", "right here", "let me
show you"); ffmpeg scene changes (new slide, new view); and YouTube's "most
replayed" peaks. The top picks are captured from a ≤720p download, then
near-duplicate frames are dropped (perceptual hash). They appear inline in the
transcript at the moment they occur, plus a gallery in the HTML.

## 2. Write the summary (always)

The run puts a placeholder (auto-picked key sentences) in the Summary section.
Replace it with a real one:

1. Read the `.md` the run reported (`INFO: Saved md: ...`). For a long video,
   read the Transcript section in chunks. If screenshots were taken and the
   video is technical (slides, code, diagrams), look at up to four of the
   frames listed in the md to get slide content right.
2. Write the summary to a file in the scratchpad (not the Notes folder), in
   this shape — keep it tight, facts from the video only:

   ```markdown
   **TL;DR:** One or two sentences: what the video shows and its main takeaway.

   ### Key points
   - Point, with a timestamp link copied from the transcript: [04:44](https://www.youtube.com/watch?v=ID&t=284s)
   - ...

   ### Details worth keeping
   - Names, versions, commands, numbers, links, and tools mentioned

   ### Verdict
   - (Only for reviews and opinions) The creator's conclusion and caveats.
   ```

3. Put it in place (updates the md and any HTML/txt/JSON siblings, offline):

   ```bash
   python3 "<skill>/scripts/run.py" add-summary "<path to .md>" "<summary file>"
   ```

A written summary survives later re-runs of the same video, so regenerating
to add HTML or screenshots does not need step 2 again.

## 3. Report

Give the user the saved paths (`INFO: Saved ...` lines), the screenshot count,
and the summary's TL;DR. Offer the HTML for viewing when it was made.

## Failure modes

- **IP-blocked / RequestBlocked** — show the error verbatim; do not retry.
  The cache means anything fetched before still works. Suggest another network
  later. `youtube-transcript-api` is pinned on purpose; don't upgrade it to fix this.
- **Transcripts disabled / no captions in that language** — stop and say so;
  for language, list `-l` choices if the error names them.
- **Screenshots skipped** with a "Video download failed" warning — usually
  no JavaScript runtime for yt-dlp's YouTube challenge. Node, Deno, or Bun on
  PATH fixes it; the transcript and notes are still written.
- **`-m full` missing deps** — inside the venv:
  `pip install "deepmultilingualpunctuation>=1.0" "transformers<5" nltk`, or drop `-m full`.
- **Bad ID** (not 11 characters) — ask the user for the URL rather than guessing.

Warnings and errors are also logged to `yt-transcript.log` in the cache folder
(`%LOCALAPPDATA%\yt-transcript`, `~/Library/Caches/yt-transcript`, or
`~/.cache/yt-transcript`).
