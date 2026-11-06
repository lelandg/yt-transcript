"""Pick and capture screenshots at the moments that matter.

Candidate moments come from up to four signals, each with a weight:

* chapters  - the creator's own chapter starts (strong, but often a title card)
* cues      - the speaker pointing at the screen: "as you can see", "this slide",
              "right here", "let me show you"... (deictic phrases)
* scenes    - ffmpeg scene-change detection: a new slide or a cut to a new view
* heatmap   - YouTube's "most replayed" peaks, when the video has them

Candidates within a few seconds of each other merge (a cue that lands on a
scene change is a much better bet than either alone). The best are captured,
then near-duplicate frames are dropped with a 256-bit difference hash, so a
talking-head video does not yield ten copies of the same face.
"""

from __future__ import annotations

import logging
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from .fetch import ffmpeg_exe, first_line, ytdlp_opts
from .models import Chapter, Segment, Shot, VideoData, fmt_time, watch_url
from .text import clean_caption

log = logging.getLogger("yt_transcript")

MODES = ("auto", "chapters", "cues", "scenes", "heatmap")

# (pattern, weight, seconds to wait after the phrase before the visual is on screen)
_CUE_PATTERNS: list[tuple[str, float, float]] = [
    (r"as you can see|you can see (?:here|that|this|the)", 3.0, 0.5),
    (r"on (?:the|my|your) screen|on[- ]screen", 3.0, 0.5),
    (r"(?:this|the next|next|that) (?:slide|diagram|chart|graph|table|figure|screenshot|code|screen|window|menu|page|example|demo)", 3.0, 0.5),
    (r"let me show you|i'?ll show you|i'?m going to show you|here'?s what (?:it|that|this) looks like", 2.5, 2.5),
    (r"take a look|look at (?:this|that|the|these|here)|check (?:this|that) out", 2.5, 1.0),
    (r"right here|over here|up here|down here|in here|here you (?:can|see|have)|here we (?:have|go|are|see)", 2.5, 0.5),
    (r"shown here|as shown|displayed|highlighted|notice (?:that|how|the)", 2.0, 0.5),
    (r"\bhere\b|\bthis one\b|\bthese\b", 0.75, 0.5),
]
_CUE_RES = [(re.compile(p, re.I), w, d) for p, w, d in _CUE_PATTERNS]

WEIGHT_CHAPTER = 3.0
WEIGHT_HEATMAP = 1.5
MERGE_WINDOW = 6.0
HASH_SIZE = 16  # 256-bit difference hash
DUP_FRACTION = 0.10  # bits that may differ and still count as the same picture
DUP_FRACTION_CHAPTER = 0.04  # chapter frames are kept unless practically identical


@dataclass
class Candidate:
    time: float
    score: float
    reasons: list[str] = field(default_factory=list)
    is_scene: bool = False


# --------------------------------------------------------------------------- signals


def chapter_candidates(chapters: list[Chapter]) -> list[Candidate]:
    # A beat into the chapter, past the transition into it.
    return [
        Candidate(c.start + min(3.0, max(0.5, (c.end - c.start) / 4)), WEIGHT_CHAPTER, [f"Chapter: {c.title}"])
        for c in chapters
    ]


def cue_candidates(segments: list[Segment]) -> list[Candidate]:
    out = []
    for seg in segments:
        text = clean_caption(seg.text)
        best: tuple[float, float, str] | None = None
        for rx, weight, delay in _CUE_RES:
            m = rx.search(text)
            if m and (best is None or weight > best[0]):
                frac = m.start() / max(len(text), 1)
                best = (weight, seg.start + seg.duration * frac + delay, m.group(0))
        if best:
            out.append(Candidate(best[1], best[0], [f'Speaker cue: "{best[2]}"']))
    return out


def heatmap_candidates(heatmap: list[dict], top: int = 5) -> list[Candidate]:
    pts = [h for h in heatmap if isinstance(h, dict) and "start_time" in h]
    if len(pts) < 3:
        return []
    peaks = []
    for i, h in enumerate(pts):
        v = h.get("value", 0)
        left = pts[i - 1].get("value", 0) if i else -1
        right = pts[i + 1].get("value", 0) if i + 1 < len(pts) else -1
        if v >= left and v >= right and v >= 0.5:
            peaks.append(h)
    peaks.sort(key=lambda h: h.get("value", 0), reverse=True)
    return [
        Candidate((h["start_time"] + h.get("end_time", h["start_time"])) / 2, WEIGHT_HEATMAP * h.get("value", 1), ["Most replayed"])
        for h in peaks[:top]
    ]


def scene_candidates(ffmpeg: str, video: Path, threshold: float = 0.3) -> list[Candidate]:
    """Visual scene changes, decoded from keyframes only (fast)."""
    cmd = [
        ffmpeg, "-hide_banner", "-nostats", "-skip_frame", "nokey", "-i", str(video),
        "-vf", f"scale=320:-2,select='gt(scene,{threshold})',metadata=print",
        "-an", "-f", "null", "-",
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=900)
    except (OSError, subprocess.TimeoutExpired) as e:
        log.warning("Scene detection failed: %s", e)
        return []
    out: list[Candidate] = []
    t = None
    for line in proc.stderr.splitlines():
        m = re.search(r"pts_time:([\d.]+)", line)
        if m:
            t = float(m.group(1))
            continue
        m = re.search(r"lavfi\.scene_score=([\d.]+)", line)
        if m and t is not None:
            s = float(m.group(1))
            # +1s so a transition has finished and the new view is settled.
            out.append(Candidate(t + 1.0, 1.0 + 2.0 * s, [f"Scene change ({s:.2f})"], is_scene=True))
            t = None
    return out


def interval_candidates(duration: float, every: float) -> list[Candidate]:
    n = int(duration // every)
    return [Candidate(every * (i + 1), 1.0, ["Interval"]) for i in range(n) if every * (i + 1) < duration - 1]


# --------------------------------------------------------------------------- selection


def merge(cands: list[Candidate], window: float = MERGE_WINDOW) -> list[Candidate]:
    """Merge nearby candidates; scores add, so agreeing signals win."""
    merged: list[Candidate] = []
    for c in sorted(cands, key=lambda c: c.time):
        last = merged[-1] if merged else None
        if last and c.time - last.time <= window:
            # Anchor on the scene change if there is one; else on the stronger signal.
            if c.is_scene and not last.is_scene:
                last.time, last.is_scene = c.time, True
            elif c.score > last.score and not last.is_scene:
                last.time = c.time
            last.score += c.score
            last.reasons += [r for r in c.reasons if r not in last.reasons]
        else:
            merged.append(Candidate(c.time, c.score, list(c.reasons), c.is_scene))
    return merged


def select(cands: list[Candidate], limit: int, min_gap: float, duration: float) -> list[Candidate]:
    picked: list[Candidate] = []
    for c in sorted(cands, key=lambda c: c.score, reverse=True):
        if duration and not (0 <= c.time < duration - 0.5):
            continue
        if all(abs(c.time - p.time) >= min_gap for p in picked):
            picked.append(c)
        if len(picked) >= limit:
            break
    return picked


def default_limit(duration: float) -> int:
    """About one shot per minute, between 6 and 24."""
    return max(6, min(24, round(duration / 60))) if duration else 12


# --------------------------------------------------------------------------- capture


def download_video(video_id: str, workdir: Path, max_height: int) -> Path | None:
    try:
        import yt_dlp
    except ImportError:
        log.warning("yt-dlp not installed; cannot capture screenshots")
        return None
    fmt = (
        f"bv*[height<={max_height}][vcodec^=avc1]/bv*[height<={max_height}]"
        f"/b[height<={max_height}]/bv*/b"
    )
    opts = ytdlp_opts(format=fmt, outtmpl=str(workdir / "%(id)s.%(ext)s"), retries=3)
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(watch_url(video_id), download=True)
            path = Path(ydl.prepare_filename(info))
    except Exception as e:
        log.warning("Video download failed (%s); no screenshots", first_line(e))
        return None
    if path.exists():
        return path
    found = sorted(workdir.glob(f"{video_id}.*"))
    return found[0] if found else None


def grab_frame(ffmpeg: str, video: Path, t: float, out: Path, width: int = 1280) -> bool:
    cmd = [
        ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{t:.2f}", "-i", str(video),
        "-frames:v", "1", "-vf", f"scale='min({width},iw)':-2", "-q:v", "3", str(out),
    ]
    try:
        subprocess.run(cmd, capture_output=True, timeout=60, check=True)
    except (OSError, subprocess.SubprocessError):
        return False
    return out.exists() and out.stat().st_size > 0


def dhash(ffmpeg: str, image: Path, size: int = HASH_SIZE) -> int | None:
    """Difference hash (size*size bits): shrink to gray, compare horizontal neighbours.

    16x16 rather than the classic 8x8: a camera pointed at a monitor makes
    every frame look alike at 8x8, and real on-screen changes get lost.
    """
    w = size + 1
    cmd = [ffmpeg, "-hide_banner", "-loglevel", "error", "-i", str(image),
           "-vf", f"scale={w}:{size}:flags=area,format=gray", "-f", "rawvideo", "-"]
    try:
        px = subprocess.run(cmd, capture_output=True, timeout=30, check=True).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    if len(px) < w * size:
        return None
    bits = 0
    for row in range(size):
        for col in range(size):
            bits = (bits << 1) | (px[row * w + col] > px[row * w + col + 1])
    return bits


def _hamming(a: int, b: int) -> int:
    return bin(a ^ b).count("1")


def shot_filename(t: float) -> str:
    return "shot_" + fmt_time(t).replace(":", "-") + ".jpg"


def capture(
    data: VideoData,
    assets_dir: Path,
    rel_prefix: str,
    *,
    mode: str = "auto",
    extra_times: list[float] | None = None,
    interval: float | None = None,
    limit: int | None = None,
    min_gap: float = 8.0,
    max_height: int = 720,
    keep_video: Path | None = None,
) -> list[Shot]:
    """Choose moments, download the video once, grab and dedupe frames."""
    ffmpeg = ffmpeg_exe()
    if not ffmpeg:
        log.warning("ffmpeg not found (install it or `pip install imageio-ffmpeg`); no screenshots")
        return []
    limit = default_limit(data.duration) if limit is None else limit
    if limit <= 0 and not extra_times:
        return []

    cands: list[Candidate] = []
    if mode in ("auto", "chapters"):
        cands += chapter_candidates(data.chapters)
    if mode in ("auto", "cues"):
        cands += cue_candidates(data.segments)
    if mode in ("auto", "heatmap"):
        cands += heatmap_candidates(data.heatmap)
    if interval:
        cands += interval_candidates(data.duration, interval)
    forced = [Candidate(t, 100.0, ["Requested"]) for t in (extra_times or [])]

    with tempfile.TemporaryDirectory(prefix="ytt-", ignore_cleanup_errors=True) as tmp:
        log.info("Downloading video (<= %dp, video only) for screenshots...", max_height)
        video = download_video(data.video_id, Path(tmp), max_height)
        if not video:
            return []
        if mode in ("auto", "scenes"):
            log.info("Detecting scene changes...")
            scenes = scene_candidates(ffmpeg, video)
            log.info("  %d scene changes", len(scenes))
            cands += scenes
        if not cands and not forced:
            log.info("No moments found; falling back to fixed intervals")
            cands = interval_candidates(data.duration, max(30.0, data.duration / limit))

        merged = merge(cands)
        # Oversample: some frames will be dropped as duplicates.
        chosen = forced + select(merged, int(limit * 1.6) + 2, min_gap, data.duration)
        chosen.sort(key=lambda c: c.score, reverse=True)

        assets_dir.mkdir(parents=True, exist_ok=True)
        for old in assets_dir.glob("shot_*.jpg"):
            old.unlink()

        kept: list[tuple[Shot, int | None]] = []
        dropped = 0
        for c in chosen:
            if len(kept) >= limit + len(forced):
                break
            out = assets_dir / shot_filename(c.time)
            if out.exists():
                continue
            if not grab_frame(ffmpeg, video, c.time, out):
                continue
            h = dhash(ffmpeg, out)
            is_forced = c.score >= 100.0
            is_chapter = any(r.startswith("Chapter:") for r in c.reasons)
            limit_bits = int(HASH_SIZE * HASH_SIZE * (DUP_FRACTION_CHAPTER if is_chapter else DUP_FRACTION))
            if h is not None and not is_forced and any(
                kh is not None and _hamming(h, kh) <= limit_bits for _, kh in kept
            ):
                out.unlink()
                dropped += 1
                continue
            kept.append((Shot(c.time, f"{rel_prefix}/{out.name}", c.reasons, round(c.score, 2)), h))
        if dropped:
            log.info("  dropped %d near-duplicate frames", dropped)
        if keep_video:
            keep_video.mkdir(parents=True, exist_ok=True)
            shutil.copy2(video, keep_video / video.name)
            log.info("Kept video: %s", keep_video / video.name)

    shots = sorted((s for s, _ in kept), key=lambda s: s.time)
    log.info("Captured %d screenshots", len(shots))
    return shots
