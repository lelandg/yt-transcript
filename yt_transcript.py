#!/usr/bin/env python3
"""Turn a YouTube video into readable notes in one run.

Default output is a Markdown file with metadata, a summary section, chapters,
and the transcript reformatted into timestamped paragraphs (each timestamp
links to that moment in the video). Options add HTML, plain text, JSON, and
screenshots captured at the moments that matter.

Usage:
    python yt_transcript.py <url-or-id> [options]

Examples:
    python yt_transcript.py https://youtu.be/dQw4w9WgXcQ
    python yt_transcript.py dQw4w9WgXcQ --html --screenshots
    python yt_transcript.py dQw4w9WgXcQ --all                 # every output + screenshots
    python yt_transcript.py dQw4w9WgXcQ --screenshots cues --max-shots 8
    python yt_transcript.py dQw4w9WgXcQ --shot-times 1:30 4:05 --html
    python yt_transcript.py dQw4w9WgXcQ -l es -o "Mi video"
    python yt_transcript.py dQw4w9WgXcQ --raw --no-timestamps  # old one-caption-per-line text

Output folder: -d wins; else <project root or working folder>/Notes; else
this tool's own Notes folder. See ytt/paths.py.
"""

from __future__ import annotations

import argparse
import logging
import re
import sys
import time
from pathlib import Path

from ytt import fetch, paths, render, shots as shotmod, summary, text
from ytt.models import Paragraph, parse_time

log = logging.getLogger("yt_transcript")


def setup_logging(verbose: bool, quiet: bool) -> None:
    level = logging.DEBUG if verbose else logging.WARNING if quiet else logging.INFO
    for stream in (sys.stdout, sys.stderr):
        try:  # Windows consoles default to a legacy code page; titles are often non-ASCII
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError):
            pass
    # main() may run more than once in a process (tests, callers): drop and
    # close only the handlers a previous call added; keep any the caller set.
    for h in [h for h in log.handlers if getattr(h, "_ytt_owned", False)]:
        log.removeHandler(h)
        h.close()
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
    console.setLevel(level)
    console._ytt_owned = True  # type: ignore[attr-defined]
    log.setLevel(logging.DEBUG)
    log.addHandler(console)
    # Warnings and errors also go to a per-user log file, on every OS.
    try:
        logfile = fetch.cache_dir() / "yt-transcript.log"
        logfile.parent.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(logfile, encoding="utf-8")
        fh.setLevel(logging.WARNING)
        fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        fh._ytt_owned = True  # type: ignore[attr-defined]
        log.addHandler(fh)
    except OSError:
        pass


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Turn a YouTube video into Markdown notes (summary, chapters, timestamped transcript), "
        "optionally with HTML, text, JSON, and screenshots.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("url", help="YouTube URL (watch, youtu.be, shorts, embed, live) or 11-character video ID")
    p.add_argument("output_pos", nargs="?", default=None, help=argparse.SUPPRESS)

    g = p.add_argument_group("where")
    g.add_argument("-o", "--output", help="Base filename (extension ignored). Default: the video title")
    g.add_argument("-d", "--directory", help="Exact output folder (overrides --base-dir)")
    g.add_argument("--base-dir", help="Caller's working folder; notes go to its project root's Notes/. Default: current folder")

    g = p.add_argument_group("outputs (Markdown is always written)")
    g.add_argument("--html", action="store_true", help="Also write a standalone HTML page (search, gallery, dark mode)")
    g.add_argument("--txt", action="store_true", help="Also write plain text")
    g.add_argument("--json", action="store_true", help="Also write JSON (metadata, segments, paragraphs, shots)")
    g.add_argument("--all", action="store_true", help="Everything: --html --txt --json --screenshots auto")
    g.add_argument("--self-contained", action="store_true", help="Embed screenshots in the HTML (one portable file)")

    g = p.add_argument_group("transcript")
    g.add_argument("-l", "--lang", nargs="+", default=None, help="Preferred caption language(s), e.g. -l en es")
    g.add_argument("--raw", action="store_true", help="No reformatting: one caption line per line")
    g.add_argument("--no-timestamps", action="store_true", help="Omit the per-paragraph timestamps")
    g.add_argument("-m", "--reformat-model", choices=["light", "full"], default="light",
                   help="light (default, no extra deps) or full (ML punctuation; needs deepmultilingualpunctuation)")
    g.add_argument("-p", "--paragraph-sentences", type=int, default=4, help="Max sentences per paragraph (default 4)")
    # Old flags: timestamps and reformatting are now the default.
    g.add_argument("-t", "--timestamps", action="store_true", help=argparse.SUPPRESS)
    g.add_argument("-r", "--reformat", action="store_true", help=argparse.SUPPRESS)

    g = p.add_argument_group("summary")
    g.add_argument("--summary-file", help="Markdown file with a written summary to put in the Summary section")
    g.add_argument("--summary-sentences", type=int, default=5, help="Sentences in the auto-extracted summary (default 5; 0 = none)")

    g = p.add_argument_group("screenshots")
    g.add_argument("-s", "--screenshots", nargs="?", const="auto", choices=shotmod.MODES, default=None,
                   help="Capture frames. auto (default) combines chapters, speaker cues, scene changes, and replay peaks")
    g.add_argument("--shot-times", nargs="+", metavar="T", default=[], help="Also capture at these times (90, 1:30, 1m30s)")
    g.add_argument("--shot-interval", type=float, metavar="SECS", help="Also capture every SECS seconds")
    g.add_argument("--max-shots", type=int, help="Cap on screenshots (default: about one per minute, 6-24)")
    g.add_argument("--shot-height", type=int, default=720, help="Video height to download for frames (default 720)")
    g.add_argument("--keep-video", action="store_true", help="Keep the downloaded video next to the screenshots")

    g = p.add_argument_group("misc")
    g.add_argument("--refresh", action="store_true", help="Ignore the cache and refetch from YouTube")
    g.add_argument("-q", "--quiet", action="store_true", help="Only warnings and errors")
    g.add_argument("-v", "--verbose", action="store_true", help="Debug logging")
    return p


def _same_video(md_path: Path, video_id: str) -> bool:
    """True when the notes file at md_path was written for this video."""
    try:
        head = md_path.read_text(encoding="utf-8").split(summary.MD_START, 1)[0]
    except OSError:
        return False
    return f"v={video_id}" in head


def _existing_written_summary(md_path: Path, video_id: str) -> str | None:
    """Keep a summary someone already wrote when the same video's notes are regenerated."""
    try:
        t = md_path.read_text(encoding="utf-8")
    except OSError:
        return None
    # Same filename, different video (e.g. a reused -o name): never carry it over.
    if f"v={video_id}" not in t.split(summary.MD_START, 1)[0]:
        return None
    m = re.search(re.escape(summary.MD_START) + r"\n?(.*?)\n?" + re.escape(summary.MD_END), t, re.S)
    if not m:
        return None
    s = m.group(1).strip()
    if not s or render.AUTO_SUMMARY_NOTE in s or s == "_No summary yet._":
        return None
    return s


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    setup_logging(args.verbose, args.quiet)
    t0 = time.monotonic()

    if args.all:
        args.html = args.txt = args.json = True
        args.screenshots = args.screenshots or "auto"
    if args.shot_times or args.shot_interval:
        args.screenshots = args.screenshots or "auto"

    try:
        video_id = fetch.extract_video_id(args.url)
        extra_times = [parse_time(t) for t in args.shot_times]
    except ValueError as e:
        log.error("%s", e)
        return 1
    log.info("Video ID: %s", video_id)

    try:
        data = fetch.get_video(video_id, args.lang, refresh=args.refresh)
    except Exception as e:
        # Keep the whole message: youtube-transcript-api puts the actionable part
        # (blocked IP, available languages) after a generic first line.
        msg = str(e).strip() or "(no message)"
        log.error("Failed to fetch transcript (%s): %s", type(e).__name__, msg)
        log.debug("details", exc_info=True)
        return 1
    log.info("Video title: %s", data.title)

    # Transcript -> paragraphs
    if args.raw:
        paragraphs = [
            Paragraph(t, t, s, text.chapter_at(t, data.chapters)) for t, s in text.plain_lines(data.segments)
        ]
    else:
        paragraphs = text.build_paragraphs(
            data.segments, data.chapters,
            sentences_per_paragraph=args.paragraph_sentences, model=args.reformat_model,
        )

    # Where and what name
    out_dir, why = paths.resolve_output_dir(args.directory, args.base_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    name = args.output or args.output_pos
    stem = paths.sanitize_filename(paths.strip_note_suffix(Path(name).name) if name else data.title)
    md_path = out_dir / f"{stem}.md"
    if md_path.exists() and not _same_video(md_path, data.video_id):
        # Another video already owns this name (same title, or a reused -o):
        # never overwrite its notes or delete its screenshots. Every fallback
        # name is checked the same way, since it can be taken too.
        base, n = stem, 1
        while md_path.exists() and not _same_video(md_path, data.video_id):
            stem = f"{base} [{data.video_id}]" + (f" {n}" if n > 1 else "")
            md_path = out_dir / f"{stem}.md"
            n += 1
        log.warning("%s.md belongs to another video; writing %s.md instead", base, stem)
    log.info("Output folder: %s (%s)", out_dir, why)

    # Screenshots
    shots = []
    if args.screenshots:
        assets = out_dir / f"{stem}_files"
        shots = shotmod.capture(
            data, assets, f"{stem}_files",
            mode=args.screenshots, extra_times=extra_times, interval=args.shot_interval,
            limit=args.max_shots, max_height=args.shot_height,
            keep_video=assets if args.keep_video else None,
        )

    # Summary: given file > one already written in these notes > extractive
    written = None
    if args.summary_file:
        try:
            written = Path(args.summary_file).read_text(encoding="utf-8")
        except OSError as e:
            log.error("Cannot read --summary-file: %s", e)
            return 1
    else:
        written = _existing_written_summary(md_path, data.video_id)
        if written:
            log.info("Keeping the written summary already in %s", md_path.name)
    auto = [] if written else summary.extractive(paragraphs, args.summary_sentences)
    summary_md = render.summary_block_md(auto, data, written)

    # Sibling outputs from an earlier run of this video are rewritten too, so
    # they never point at screenshots this run replaced or removed.
    for kind in ("html", "txt", "json"):
        if not getattr(args, kind) and md_path.with_suffix(f".{kind}").exists() and _same_video(md_path, data.video_id):
            setattr(args, kind, True)
            log.info("Also refreshing the existing %s", md_path.with_suffix(f".{kind}").name)

    ts = not args.no_timestamps
    outputs = {"md": md_path}
    md_path.write_text(render.render_md(data, paragraphs, shots, summary_md, timestamps=ts), encoding="utf-8")
    if args.html:
        outputs["html"] = md_path.with_suffix(".html")
        outputs["html"].write_text(
            render.render_html(data, paragraphs, shots, summary_md, out_dir, timestamps=ts, embed_images=args.self_contained),
            encoding="utf-8",
        )
    if args.txt:
        outputs["txt"] = md_path.with_suffix(".txt")
        outputs["txt"].write_text(render.render_txt(data, paragraphs, shots, summary_md, timestamps=ts), encoding="utf-8")
    if args.json:
        outputs["json"] = md_path.with_suffix(".json")
        outputs["json"].write_text(render.render_json(data, paragraphs, shots, summary_md), encoding="utf-8")

    words = sum(len(p.text.split()) for p in paragraphs if not p.is_cue)
    log.info(
        "Done in %.1fs: %d paragraphs, %d words, %d chapters, %d screenshots",
        time.monotonic() - t0, len(paragraphs), words, len(data.chapters), len(shots),
    )
    for kind, path in outputs.items():
        log.info("Saved %s: %s", kind, path)
    if shots:
        log.info("Saved screenshots: %s", out_dir / f"{stem}_files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
