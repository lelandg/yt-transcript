# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.1] - 2026-11-06

### Fixed
- `run.sh` failed under WSL, Linux, and macOS when the repo was checked out on Windows (`set: pipefail: invalid option name`): `.gitattributes` now keeps `*.sh` and `*.py` at LF endings.
- The launcher no longer reinstalls requirements when Windows and WSL share one checkout; its requirements hash ignores line endings.

## [0.1.0] - 2026-11-06

### Added
- One run writes Markdown notes: metadata, a Summary section, chapters, and the transcript formatted into paragraphs, each with a timestamp link into the video. Timestamps and reformatting no longer need separate runs.
- `--html` page with search, screenshot gallery and lightbox, chapter links, dark mode, and print styles; `--self-contained` embeds the images. Also `--txt`, `--json`, and `--all`.
- Screenshots (`-s auto|chapters|cues|scenes|heatmap`, `--shot-times`, `--shot-interval`, `--max-shots`). Auto mode merges chapter starts, speaker cue phrases ("as you can see", "this slide"), ffmpeg scene changes, and "most replayed" peaks, then drops near-duplicates with a 256-bit difference hash. Shots appear inline at their moment.
- Extractive summary fallback, and `add_summary.py` (`run.py add-summary`) to put a written summary into every format without refetching. Re-runs keep a written summary.
- Per-video cache of metadata and captions in the OS cache folder (`--refresh` to bypass). Warnings and errors are also logged to `yt-transcript.log` there.
- Cross-platform launcher `scripts/run.py`: per-OS venv, installs only when `requirements.txt` changes, finds or clones the checkout, never changes directory.

### Changed
- Notes go to the caller's project: the git root of `--base-dir` (default: current folder) or the folder itself, plus `/Notes`; this repo's `Notes/` only when there is no usable folder.
- Inline `[music]` tags no longer split sentences; vocal-noise tags are dropped; `>>` speaker changes start a new paragraph.
- `-t` and `-r` are accepted but no longer needed. `--raw` gives the old one-caption-per-line output.
- Dependencies pinned: `youtube-transcript-api==1.2.4`, `yt-dlp[default]==2026.10.26`, `imageio-ffmpeg==0.6.0`.

## [0.0.1] - 2026-04-21

### Changed
- docs: add README with usage examples and feature overview
- Merge pull request #1 from lelandg/claude/yt-transcript-skill
- Add Claude Code skill and slash command for yt-transcript
- Add .claude settings, update README, ignore .idea
- Initial commit: YouTube transcript downloader
