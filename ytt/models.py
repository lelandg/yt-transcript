"""Plain data containers shared by the fetch, format, and render stages."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field


@dataclass
class Segment:
    """One caption line as YouTube delivers it."""

    start: float
    duration: float
    text: str


@dataclass
class Chapter:
    start: float
    end: float
    title: str


@dataclass
class Paragraph:
    start: float
    end: float
    text: str
    chapter: int | None = None  # index into VideoData.chapters
    is_cue: bool = False  # a "[music]"-style sound cue rather than speech


@dataclass
class Shot:
    """A captured frame and why it was chosen."""

    time: float
    file: str  # path relative to the notes file
    reasons: list[str] = field(default_factory=list)
    score: float = 0.0


@dataclass
class VideoData:
    video_id: str
    url: str
    title: str
    channel: str = ""
    channel_url: str = ""
    upload_date: str = ""  # YYYY-MM-DD
    duration: float = 0.0
    view_count: int | None = None
    description: str = ""
    thumbnail: str = ""
    tags: list[str] = field(default_factory=list)
    chapters: list[Chapter] = field(default_factory=list)
    heatmap: list[dict] = field(default_factory=list)  # [{start_time, end_time, value}]
    language: str = ""
    is_generated: bool | None = None
    segments: list[Segment] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "VideoData":
        d = dict(d)
        d["chapters"] = [Chapter(**c) for c in d.get("chapters", [])]
        d["segments"] = [Segment(**s) for s in d.get("segments", [])]
        known = set(cls.__dataclass_fields__)
        return cls(**{k: v for k, v in d.items() if k in known})


def fmt_time(seconds: float) -> str:
    """Format seconds as M:SS or H:MM:SS (YouTube style)."""
    s = max(0, int(seconds))
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    return f"{h}:{m:02d}:{sec:02d}" if h else f"{m:02d}:{sec:02d}"


def parse_time(value: str) -> float:
    """Parse '90', '1:30', '01:02:03', or '1m30s' into seconds."""
    v = value.strip().lower()
    if not v:
        raise ValueError("empty time")
    if any(c in v for c in "hms") and not v.replace(".", "").isdigit():
        total = 0.0
        num = ""
        for ch in v:
            if ch.isdigit() or ch == ".":
                num += ch
            elif ch in "hms" and num:
                total += float(num) * {"h": 3600, "m": 60, "s": 1}[ch]
                num = ""
            else:
                raise ValueError(f"bad time: {value!r}")
        if num:
            total += float(num)
        return _checked_time(total, value)
    parts = v.split(":")
    if len(parts) > 3:
        raise ValueError(f"bad time: {value!r}")
    total = 0.0
    for p in parts:
        total = total * 60 + float(p)
    return _checked_time(total, value)


def _checked_time(total: float, value: str) -> float:
    """Reject inf, nan, and negative times (float() accepts all three)."""
    if not math.isfinite(total) or total < 0:
        raise ValueError(f"bad time: {value!r}")
    return total


def watch_url(video_id: str, t: float | None = None) -> str:
    base = f"https://www.youtube.com/watch?v={video_id}"
    return f"{base}&t={int(t)}s" if t is not None else base
