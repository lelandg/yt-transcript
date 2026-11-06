"""Turn timed caption segments into readable, timestamped paragraphs.

Every word keeps the time it was spoken (interpolated inside its caption
segment), so sentences and paragraphs can carry accurate timestamps. That is
what lets the output be both reformatted *and* timestamped in one pass.
"""

from __future__ import annotations

import html
import logging
import re
from dataclasses import dataclass

from .models import Chapter, Paragraph, Segment

log = logging.getLogger("yt_transcript")

_CUE_RE = re.compile(r"\[[^\]]{1,40}\]")
# Sound cues not worth a line in the notes ([music] and [applause] are kept).
_NOISE_CUE_RE = re.compile(r"clears? throat|cough|sigh|sniff|inhale|exhale|breath|snort|groan|grunt|swallow", re.I)
_SPEAKER_RE = re.compile(r"(^|\s)>>+\s*")
_WS_RE = re.compile(r"\s+")
_ABBREV = {"mr.", "mrs.", "ms.", "dr.", "st.", "vs.", "etc.", "e.g.", "i.e.", "approx.", "no."}
_DISCOURSE = {"so", "but", "because", "then", "now", "okay", "ok", "anyway", "alright"}

# Paragraph shaping defaults.
MAX_PARAGRAPH_WORDS = 110
PAUSE_SENTENCE = 1.2  # seconds of silence that ends an unpunctuated sentence
PAUSE_PARAGRAPH = 3.0  # seconds of silence that starts a new paragraph
MAX_PUNCTUATED_SENTENCE_WORDS = 60


@dataclass
class Word:
    text: str
    time: float
    speaker_change: bool = False  # a ">>" marker preceded this word
    gap_before: float = 0.0  # silence between this word's segment and the previous one


@dataclass
class Sentence:
    words: list[Word]
    text: str = ""

    @property
    def start(self) -> float:
        return self.words[0].time

    @property
    def end(self) -> float:
        return self.words[-1].time


@dataclass
class _Cue:
    time: float
    label: str


def clean_caption(text: str) -> str:
    """Unescape HTML entities and collapse whitespace in one caption line."""
    text = html.unescape(text).replace("\n", " ")
    return _WS_RE.sub(" ", text).strip()


def tokenize(segments: list[Segment]) -> list[Word | _Cue]:
    """Flatten segments into timed words, keeping standalone sound cues."""
    items: list[Word | _Cue] = []
    prev_end: float | None = None
    for i, seg in enumerate(segments):
        text = clean_caption(seg.text)
        if not text:
            continue
        # Auto-captions overlap; a segment really ends where the next begins.
        nxt = segments[i + 1].start if i + 1 < len(segments) else None
        dur = seg.duration
        if nxt is not None and seg.start < nxt < seg.start + dur:
            dur = nxt - seg.start
        gap = 0.0 if prev_end is None else max(0.0, seg.start - prev_end)
        prev_end = seg.start + dur

        speech = _CUE_RE.sub(" ", text)
        if not _SPEAKER_RE.sub(" ", speech).strip():
            # Segment holds only cues like "[music]" or ">> [applause]".
            for m in _CUE_RE.finditer(text):
                if not _NOISE_CUE_RE.search(m.group(0)):
                    items.append(_Cue(seg.start, m.group(0).lower()))
            continue

        # Mark speaker changes, then drop inline cues mid-sentence.
        parts = re.split(r"(>>+)", speech)
        tokens: list[tuple[str, bool]] = []
        pending_speaker = False
        for part in parts:
            if part.startswith(">>"):
                pending_speaker = True
                continue
            for w in part.split():
                tokens.append((w, pending_speaker))
                pending_speaker = False
        n = len(tokens)
        for j, (w, spk) in enumerate(tokens):
            items.append(
                Word(
                    text=w,
                    time=seg.start + dur * j / max(n, 1),
                    speaker_change=spk,
                    gap_before=gap if j == 0 else 0.0,
                )
            )
    return items


def is_punctuated(words: list[Word]) -> bool:
    """True when the captions already carry sentence punctuation."""
    if not words:
        return False
    enders = sum(1 for w in words if w.text[-1:] in ".!?")
    return enders / len(words) > 0.02


def _ends_sentence(word: str) -> bool:
    w = word.lower().rstrip("\"')]")
    if not w or w[-1] not in ".!?":
        return False
    return w not in _ABBREV


def split_sentences(words: list[Word], punctuated: bool) -> list[Sentence]:
    """Group timed words into sentences, using punctuation or pauses and cue words."""
    sentences: list[Sentence] = []
    cur: list[Word] = []

    def flush() -> None:
        if cur:
            sentences.append(Sentence(list(cur)))
            cur.clear()

    for w in words:
        if cur and not punctuated:
            n = len(cur)
            if (
                (w.gap_before >= PAUSE_SENTENCE and n >= 4)
                or (w.text.lower().strip(",") in _DISCOURSE and n >= 8)
                or n >= 24
            ):
                flush()
        if cur and punctuated and len(cur) >= MAX_PUNCTUATED_SENTENCE_WORDS:
            flush()  # captions with sparse punctuation still get sentence breaks
        if cur and w.speaker_change:
            flush()
        cur.append(w)
        if punctuated and _ends_sentence(w.text):
            flush()
    flush()
    for s in sentences:
        s.text = _finish_sentence(" ".join(w.text for w in s.words), add_period=not punctuated)
    return sentences


def _finish_sentence(s: str, add_period: bool) -> str:
    s = s.strip()
    if not s:
        return s
    s = s[0].upper() + s[1:]
    s = re.sub(r"\bi\b(?!\.e\.)", "I", s)
    s = re.sub(r"\bi'(m|ve|ll|d)\b", lambda m: "I'" + m.group(1), s)
    if s[-1] in ",;:":
        s = s[:-1]
    if s.rstrip(")]\"'”’")[-1:] not in ".!?":
        s += "."
    return s


def restore_punctuation(words: list[Word]) -> bool:
    """Apply the ML punctuation model in place. Returns False if unavailable."""
    try:
        from deepmultilingualpunctuation import PunctuationModel
    except ImportError:
        return False
    plain = [re.sub(r"[.,!?;:]+$", "", w.text) or w.text for w in words]
    restored = PunctuationModel().restore_punctuation(" ".join(plain)).split()
    if len(restored) != len(words):
        return False
    for w, r in zip(words, restored):
        w.text = r
    return True


def chapter_at(t: float, chapters: list[Chapter]) -> int | None:
    """Index of the chapter that time t falls in, or None before the first."""
    idx = None
    for i, c in enumerate(chapters):
        # Speech often starts a beat before the chapter marker the creator set.
        if c.start <= t + 1.5:
            idx = i
    return idx


def build_paragraphs(
    segments: list[Segment],
    chapters: list[Chapter] | None = None,
    *,
    sentences_per_paragraph: int = 4,
    model: str = "light",
) -> list[Paragraph]:
    """Group captions into paragraphs that break on chapters, pauses, and speakers."""
    chapters = chapters or []
    items = tokenize(segments)
    words = [it for it in items if isinstance(it, Word)]
    punctuated = is_punctuated(words)
    if model == "full":
        if restore_punctuation(words):
            punctuated = True
        else:
            log.warning(
                "-m full did not run (needs: pip install \"deepmultilingualpunctuation>=1.0\" \"transformers<5\" nltk "
                "in the venv, or the model changed the word count); used light formatting instead"
            )
    sentences = split_sentences(words, punctuated)

    # Interleave sentences with standalone cues by time.
    cues = [it for it in items if isinstance(it, _Cue)]
    stream: list[Sentence | _Cue] = sorted(
        [*sentences, *cues], key=lambda x: x.time if isinstance(x, _Cue) else x.start
    )

    paragraphs: list[Paragraph] = []
    cur: list[Sentence] = []
    cur_chapter: int | None = None
    n_per = max(1, sentences_per_paragraph)

    def flush() -> None:
        if cur:
            paragraphs.append(
                Paragraph(
                    start=cur[0].start,
                    end=cur[-1].end,
                    text=" ".join(s.text for s in cur),
                    chapter=cur_chapter,
                )
            )
            cur.clear()

    pending_cue: _Cue | None = None

    def emit_cue() -> None:
        nonlocal pending_cue
        c = pending_cue
        pending_cue = None
        if c is None or (paragraphs and paragraphs[-1].is_cue and paragraphs[-1].text == c.label):
            return
        paragraphs.append(Paragraph(c.time, c.time, c.label, chapter_at(c.time, chapters), True))

    for item in stream:
        if isinstance(item, _Cue):
            # Sound cues ("[music]") only show where a paragraph breaks anyway,
            # so they never cut a thought in half.
            if not cur and not paragraphs:
                pending_cue = item
                emit_cue()
            elif pending_cue is None:
                pending_cue = item
            continue
        ch = chapter_at(item.start, chapters)
        words_in = sum(len(s.words) for s in cur)
        new_par = bool(cur) and (
            ch != cur_chapter
            or len(cur) >= n_per
            or words_in + len(item.words) > MAX_PARAGRAPH_WORDS
            or item.words[0].gap_before >= PAUSE_PARAGRAPH
            or item.words[0].speaker_change
        )
        if new_par:
            flush()
            emit_cue()
        else:
            pending_cue = None
        if not cur:
            cur_chapter = ch
        cur.append(item)
    flush()
    emit_cue()
    return paragraphs


def plain_lines(segments: list[Segment]) -> list[tuple[float, str]]:
    """Raw one-caption-per-line output (the old default)."""
    out = []
    for s in segments:
        t = clean_caption(s.text)
        if t:
            out.append((s.start, t))
    return out
