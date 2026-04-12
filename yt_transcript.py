#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["youtube-transcript-api>=1.0.0"]
# ///
"""Download YouTube video transcripts and save to text files.

Usage:
    uv run yt_transcript.py <youtube_url> [output_filename] [options]

Examples:
    uv run yt_transcript.py "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    uv run yt_transcript.py "https://youtu.be/dQw4w9WgXcQ" my_transcript.txt
    uv run yt_transcript.py "https://youtu.be/dQw4w9WgXcQ" -o my_transcript.txt
    uv run yt_transcript.py "https://youtu.be/dQw4w9WgXcQ" -d /tmp/transcripts
    uv run yt_transcript.py "https://youtu.be/dQw4w9WgXcQ" -l es
    uv run yt_transcript.py "https://youtu.be/dQw4w9WgXcQ" -t
    uv run yt_transcript.py "https://youtu.be/dQw4w9WgXcQ" -r -m full
"""

import argparse
import html
import json
import logging
import os
import re
import sys
import urllib.error
import urllib.request

from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.formatters import TextFormatter

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)


def extract_video_id(url: str) -> str:
    """Extract the video ID from various YouTube URL formats."""
    patterns = [
        r"(?:v=|/v/|youtu\.be/|/embed/|/shorts/)([a-zA-Z0-9_-]{11})",
        r"^([a-zA-Z0-9_-]{11})$",  # bare video ID
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    raise ValueError(f"Could not extract video ID from: {url}")


def fetch_video_title(video_id: str) -> str:
    """Fetch video title via YouTube's oembed endpoint (no API key needed)."""
    oembed_url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json"
    req = urllib.request.Request(oembed_url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return html.unescape(data.get("title", video_id))
    except (urllib.error.URLError, json.JSONDecodeError, KeyError) as e:
        log.warning("Could not fetch video title (%s), using video ID as filename", e)
        return video_id


def sanitize_filename(name: str) -> str:
    """Sanitize a string for use as a filename."""
    # Replace common path-unsafe characters
    name = re.sub(r'[<>:"/\\|?*]', "", name)
    # Collapse whitespace
    name = re.sub(r"\s+", " ", name).strip()
    # Remove leading/trailing dots and spaces
    name = name.strip(". ")
    # Truncate to reasonable length
    if len(name) > 200:
        name = name[:200].rsplit(" ", 1)[0]
    return name or "transcript"


def get_transcript(video_id: str, languages: list[str] | None = None) -> str:
    """Fetch and format the transcript for a video."""
    ytt_api = YouTubeTranscriptApi()
    if languages:
        transcript = ytt_api.fetch(video_id, languages=languages)
    else:
        transcript = ytt_api.fetch(video_id)
    formatter = TextFormatter()
    return formatter.format_transcript(transcript)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Download YouTube transcript to a text file."
    )
    parser.add_argument("url", help="YouTube video URL or video ID")
    parser.add_argument(
        "output_pos",
        nargs="?",
        default=None,
        help="Output filename (positional, optional)",
    )
    parser.add_argument(
        "-o",
        "--output",
        help="Override output filename (e.g. 'my_notes.txt')",
    )
    parser.add_argument(
        "-d",
        "--directory",
        default="./Notes",
        help="Output directory (default: ./Notes)",
    )
    parser.add_argument(
        "-l",
        "--lang",
        nargs="+",
        default=None,
        help="Preferred transcript language(s), e.g. -l en es",
    )
    parser.add_argument(
        "-t",
        "--timestamps",
        action="store_true",
        help="Include timestamps in output",
    )
    parser.add_argument(
        "-r",
        "--reformat",
        action="store_true",
        help="Post-process transcript into capitalized sentences and paragraphs",
    )
    parser.add_argument(
        "-m",
        "--reformat-model",
        choices=["light", "full"],
        default="light",
        help="Reformat backend: 'light' (stdlib, default) or 'full' "
        "(deepmultilingualpunctuation, requires ~500MB model download)",
    )
    parser.add_argument(
        "-p",
        "--paragraph-sentences",
        type=int,
        default=4,
        help="Sentences per paragraph when reformatting (default: 4)",
    )
    args = parser.parse_args()

    # Extract video ID
    try:
        video_id = extract_video_id(args.url)
    except ValueError as e:
        log.error(e)
        return 1

    log.info("Video ID: %s", video_id)

    # Determine output filename (-o flag takes precedence over positional)
    output_name = args.output or args.output_pos
    if output_name:
        filename = output_name
        if not filename.endswith(".txt"):
            filename += ".txt"
    else:
        title = fetch_video_title(video_id)
        log.info("Video title: %s", title)
        filename = sanitize_filename(title) + ".txt"

    # Resolve output path
    out_dir = os.path.abspath(args.directory)
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, filename)

    # Fetch transcript
    log.info("Fetching transcript...")
    try:
        if args.timestamps:
            ytt_api = YouTubeTranscriptApi()
            if args.lang:
                transcript = ytt_api.fetch(video_id, languages=args.lang)
            else:
                transcript = ytt_api.fetch(video_id)
            lines = []
            for entry in transcript:
                mins, secs = divmod(int(entry.start), 60)
                hours, mins = divmod(mins, 60)
                ts = f"[{hours:02d}:{mins:02d}:{secs:02d}]"
                lines.append(f"{ts} {entry.text}")
            text = "\n".join(lines)
        else:
            text = get_transcript(video_id, args.lang)
    except Exception as e:
        log.error("Failed to fetch transcript: %s", e)
        return 1

    # Optional reformatting
    if args.reformat:
        if args.timestamps:
            log.warning("--reformat is incompatible with --timestamps; skipping reformat")
        else:
            from reformat import reformat as _reformat
            try:
                text = _reformat(
                    text,
                    model=args.reformat_model,
                    paragraph_sentences=args.paragraph_sentences,
                )
            except RuntimeError as e:
                log.error("%s", e)
                return 2

    # Write output
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(text)

    log.info("Saved to: %s", out_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
