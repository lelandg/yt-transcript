# One-run video notes (2026-11-06)

## Why

Getting a usable transcript took three runs: plain, `-t`, then `-r`, because
timestamps and reformatting could not be combined. Notes always landed in this
repo instead of the project being worked on, and there was no summary, HTML,
or way to capture what was on screen.

## What changed

- **One run, all features.** The transcript is formatted into paragraphs and
  timestamped by default. Every word keeps its interpolated caption time, so
  each paragraph carries an accurate `[MM:SS]` link into the video
  (`ytt/text.py`). Paragraphs break on chapters, long pauses, speaker changes
  (`>>`), sentence count, and length. Inline `[music]` tags no longer split
  sentences. Sound tags appear only between paragraphs, and noise like
  `[clears throat]` is dropped.
- **Markdown by default**, with metadata, a Summary section, chapters, the
  transcript, and the video description. Optional `--html` (search, gallery,
  lightbox, dark mode, print styles; `--self-contained` embeds images),
  `--txt`, `--json`, or `--all`.
- **Summary.** An offline extractive fallback (TF-IDF over sentences, spread
  across the video) sits between markers. `add_summary.py` (or
  `run.py add-summary`) swaps in a written summary across md, html, txt, and json
  without refetching. Re-runs keep a written summary.
- **Screenshots** (`-s [auto|chapters|cues|scenes|heatmap]`, `--shot-times`,
  `--shot-interval`, `--max-shots`). The default `auto` mode merges chapter
  starts, speaker cue phrases ("as you can see", "this slide", "right here"),
  ffmpeg keyframe scene changes, and "most replayed" peaks within 6 s, so agreeing
  signals win. The top picks are captured from a ≤720p video-only download, then
  near-duplicates are dropped with a 256-bit difference hash. Chapter frames
  get a stricter duplicate test, so each chapter usually keeps a picture.
- **Output folder** (`ytt/paths.py`): `-d`, else the git root of
  `--base-dir` (or the folder itself) + `/Notes`, else this repo's `Notes/`
  when there is no usable working folder (home, a drive root, temp).
- **Cache** of metadata and captions per video in the OS cache folder, so
  re-runs never hit YouTube's rate limit. `--refresh` bypasses it.
- **Cross-platform launcher** `scripts/run.py` replaces the logic in run.ps1
  and run.sh (now thin shims). It does not `cd`, finds the checkout
  (env var, its own repo, common paths, or clones), uses a per-OS venv, and
  reinstalls only when `requirements.txt` changes.
- **Pinned dependencies**: `youtube-transcript-api==1.2.4`,
  `yt-dlp[default]==2026.10.26`, `imageio-ffmpeg==0.6.0` (static ffmpeg for
  every OS); dev: `pytest==9.1.1`. All at least 7 days old.
- Errors and warnings are also logged to `yt-transcript.log` in the cache folder.

## Tuning notes from the test video

On `rCiLORb2QbY` (a camera filming a CRT), an 8×8 dHash threw away the whole
Windows-desktop chapter as "duplicates": every frame of a monitor on a desk
looks alike at 64 bits. A 16×16 hash (10% of bits may differ) plus a 4% limit
for chapter frames kept 12 distinct shots covering every major section.

## Verified

- `pytest`: 58 tests, all offline.
- Independent code review (Claude `code-reviewer`). Fixed: summary links could
  break out of `href`; a reused `-o` name carried one video's written summary
  into another; empty exception messages crashed the oEmbed fallback;
  `"(finally.)."` double periods; no sentence cap for sparsely punctuated
  captions; `run.ps1` aborting under Windows PowerShell 5.1 when stderr is
  captured; Windows temp-dir cleanup errors; `-o "Talk v2.0"` losing `.0`;
  plus small nits. Each has a regression test.
- End to end on Windows from another project folder with `--all --self-contained`:
  md/html/txt/json + 12 screenshots in that project's `Notes/`. The second run
  took 7.7 s from cache and kept the written summary.
- HTML in a browser: dark and light, 375 px portrait and 812×375 landscape with
  no horizontal overflow, search highlighting, lightbox, timestamp links.
- WSL (Ubuntu, Python 3.12, Node on PATH): the launcher created and filled
  `.venv_linux` itself, used imageio-ffmpeg's Linux binary, and produced the same
  12 screenshots in 13.6 s.
- Windows PowerShell 5.1 through `run.ps1`: exit 0.
- macOS was not run (no Mac available). The code paths are the POSIX ones WSL
  exercised, plus the `.venv_mac` and `~/Library/Caches` choices.

## Not done

- `-m full` (ML punctuation) was not exercised. It needs a ~500 MB model and
  optional packages that are not installed.
- The Chameleon-Labs plugin copy of this skill (`Chameleon-Labs-LLC/plugins`)
  still ships the old runner. Updating it is a separate change in that repo.
