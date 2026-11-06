"""Fetch video metadata (yt-dlp, oEmbed fallback) and the transcript, with caching.

The cache matters: YouTube rate-limits transcript requests per IP, so a re-run
(new format, added summary, different screenshot mode) should never refetch.
"""

from __future__ import annotations

import html
import json
import logging
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from .models import Chapter, Segment, VideoData, watch_url

log = logging.getLogger("yt_transcript")

CACHE_VERSION = 1


def first_line(e: BaseException) -> str:
    """First line of an exception message, or its type name when the message is empty."""
    return (str(e).strip().splitlines() or [type(e).__name__])[0]


def extract_video_id(url: str) -> str:
    """Extract the 11-character video ID from any common YouTube URL form."""
    patterns = [
        r"(?:v=|/v/|youtu\.be/|/embed/|/shorts/|/live/)([a-zA-Z0-9_-]{11})",
        r"^([a-zA-Z0-9_-]{11})$",
    ]
    for pattern in patterns:
        m = re.search(pattern, url.strip())
        if m:
            return m.group(1)
    raise ValueError(f"Could not extract video ID from: {url}")


def cache_dir() -> Path:
    """Per-user cache directory, following each OS's convention."""
    override = os.environ.get("YT_TRANSCRIPT_CACHE")
    if override:
        return Path(override)
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Caches"
    else:
        base = Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache")
    return base / "yt-transcript"


def _cache_path(video_id: str, langs: list[str] | None) -> Path:
    suffix = "-" + "_".join(langs) if langs else ""
    return cache_dir() / f"{video_id}{suffix}.json"


def load_cached(video_id: str, langs: list[str] | None) -> VideoData | None:
    p = _cache_path(video_id, langs)
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        if d.get("_cache_version") != CACHE_VERSION:
            return None
        d.pop("_cache_version", None)
        return VideoData.from_dict(d)
    except (OSError, ValueError, TypeError):
        return None


def save_cache(data: VideoData, langs: list[str] | None) -> None:
    p = _cache_path(data.video_id, langs)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        d = data.to_dict()
        d["_cache_version"] = CACHE_VERSION
        p.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    except OSError as e:
        log.warning("Could not write cache %s: %s", p, e)


# --------------------------------------------------------------------------- metadata


def ytdlp_opts(**extra) -> dict:
    """Shared yt-dlp options: quiet, any JS runtime it can find, our ffmpeg."""
    opts = {
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "socket_timeout": 30,
        # YouTube's player challenge needs a JS runtime; try what's installed.
        "js_runtimes": {"deno": {}, "node": {}, "bun": {}},
    }
    ff = ffmpeg_exe()
    if ff:
        opts["ffmpeg_location"] = ff
    opts.update(extra)
    return opts


def ffmpeg_exe() -> str | None:
    """System ffmpeg if on PATH, else the static binary from imageio-ffmpeg."""
    import shutil

    found = shutil.which("ffmpeg")
    if found:
        return found
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None


def fetch_metadata(video_id: str) -> dict:
    """Full metadata via yt-dlp; falls back to oEmbed (title + channel only)."""
    try:
        import yt_dlp

        with yt_dlp.YoutubeDL(ytdlp_opts(skip_download=True)) as ydl:
            info = ydl.extract_info(watch_url(video_id), download=False)
        return ydl.sanitize_info(info) or {}
    except ImportError:
        log.warning("yt-dlp not installed; chapters and screenshots unavailable")
    except Exception as e:  # network, bot-check, removed video...
        log.warning("yt-dlp metadata failed (%s); falling back to oEmbed", first_line(e))
    return _oembed(video_id)


def _oembed(video_id: str) -> dict:
    url = f"https://www.youtube.com/oembed?url={watch_url(video_id)}&format=json"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            d = json.loads(resp.read().decode("utf-8"))
        return {
            "title": html.unescape(d.get("title", video_id)),
            "channel": d.get("author_name", ""),
            "channel_url": d.get("author_url", ""),
            "thumbnail": d.get("thumbnail_url", ""),
        }
    except (urllib.error.URLError, ValueError, OSError) as e:
        log.warning("Could not fetch video title (%s); using the video ID", e)
        return {"title": video_id}


def _fix_mojibake(s: str) -> str:
    """Repair UTF-8 text that was decoded as cp1252 (seen in some chapter titles)."""
    try:
        fixed = s.encode("cp1252").decode("utf-8")
        return fixed
    except (UnicodeEncodeError, UnicodeDecodeError):
        return s


def _chapters(info: dict) -> list[Chapter]:
    out = []
    for c in info.get("chapters") or []:
        try:
            out.append(Chapter(float(c["start_time"]), float(c["end_time"]), _fix_mojibake(c.get("title", "")).strip()))
        except (KeyError, TypeError, ValueError):
            continue
    return out


# --------------------------------------------------------------------------- transcript


def fetch_transcript(video_id: str, langs: list[str] | None) -> tuple[list[Segment], str, bool | None]:
    """Return (segments, language label, is_generated)."""
    from youtube_transcript_api import YouTubeTranscriptApi

    api = YouTubeTranscriptApi()
    fetched = api.fetch(video_id, languages=langs) if langs else api.fetch(video_id)
    segs = [Segment(float(s.start), float(s.duration), s.text) for s in fetched]
    lang = getattr(fetched, "language", "") or getattr(fetched, "language_code", "")
    return segs, lang, getattr(fetched, "is_generated", None)


def get_video(video_id: str, langs: list[str] | None = None, *, refresh: bool = False) -> VideoData:
    """Metadata + transcript, from cache when possible."""
    if not refresh:
        cached = load_cached(video_id, langs)
        if cached:
            log.info("Using cached transcript and metadata (pass --refresh to refetch)")
            return cached

    log.info("Fetching metadata...")
    info = fetch_metadata(video_id)
    log.info("Fetching transcript...")
    t0 = time.monotonic()
    segments, lang, generated = fetch_transcript(video_id, langs)
    log.debug("Transcript fetched in %.1fs", time.monotonic() - t0)

    upload = info.get("upload_date") or ""
    if len(upload) == 8 and upload.isdigit():
        upload = f"{upload[:4]}-{upload[4:6]}-{upload[6:]}"
    duration = float(info.get("duration") or 0)
    if not duration and segments:
        duration = segments[-1].start + segments[-1].duration

    data = VideoData(
        video_id=video_id,
        url=watch_url(video_id),
        title=info.get("title") or video_id,
        channel=info.get("channel") or info.get("uploader") or "",
        channel_url=info.get("channel_url") or info.get("uploader_url") or "",
        upload_date=upload,
        duration=duration,
        view_count=info.get("view_count"),
        description=info.get("description") or "",
        thumbnail=info.get("thumbnail") or "",
        tags=list(info.get("tags") or [])[:20],
        chapters=_chapters(info),
        heatmap=list(info.get("heatmap") or []),
        language=lang,
        is_generated=generated,
        segments=segments,
    )
    save_cache(data, langs)
    return data
