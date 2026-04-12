"""Post-process raw YouTube transcript text into readable prose."""

import re

_CUE_BRACKET_RE = re.compile(r"\[[^\]]+\]")
_WS_RE = re.compile(r"\s+")
_SENT_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")
_DISCOURSE_CUES = (
    " and then ",
    " so ",
    " but ",
    " because ",
    " which ",
    " when ",
    " then ",
)
_MAX_WORDS = 20


def reformat(text: str, *, model: str = "light", paragraph_sentences: int = 4) -> str:
    """Return `text` reformatted into readable prose."""
    if model == "light":
        return _light_reformat(text, paragraph_sentences)
    if model == "full":
        return _full_reformat(text, paragraph_sentences)
    raise ValueError(f"unknown reformat model: {model!r}")


def _light_reformat(text: str, paragraph_sentences: int) -> str:
    if not text or not text.strip():
        return ""

    # Split on bracketed cue markers so they become paragraph boundaries.
    chunks = _CUE_BRACKET_RE.split(text)
    chunks = [_WS_RE.sub(" ", c).strip() for c in chunks]
    chunks = [c for c in chunks if c]

    paragraphs: list[str] = []
    for chunk in chunks:
        sentences = _split_sentences(chunk)
        sentences = [_capitalize(s) for s in sentences if s]
        if sentences:
            paragraphs.append(_paragraphize(sentences, paragraph_sentences))

    return "\n\n".join(p for p in paragraphs if p)


def _split_sentences(text: str) -> list[str]:
    if re.search(r"[.!?]", text):
        parts = _SENT_SPLIT_RE.split(text.strip())
        return [p.strip() for p in parts if p.strip()]

    # No terminal punctuation: split on discourse cues, then length-cap.
    pieces = [text.strip()]
    for cue in _DISCOURSE_CUES:
        next_pieces: list[str] = []
        for piece in pieces:
            segments = piece.split(cue)
            if len(segments) == 1:
                next_pieces.append(piece)
                continue
            next_pieces.append(segments[0].strip())
            for seg in segments[1:]:
                next_pieces.append((cue.strip() + " " + seg).strip())
        pieces = next_pieces

    capped: list[str] = []
    for piece in pieces:
        words = piece.split()
        if not words:
            continue
        for i in range(0, len(words), _MAX_WORDS):
            capped.append(" ".join(words[i : i + _MAX_WORDS]))
    return capped


def _capitalize(sentence: str) -> str:
    s = sentence.strip()
    if not s:
        return s
    s = s[0].upper() + s[1:]
    s = re.sub(r"\bi\b", "I", s)
    s = re.sub(r"\bi'(m|ve|ll|d)\b", lambda m: "I'" + m.group(1), s)
    if s[-1] not in ".!?":
        s += "."
    return s


def _full_reformat(text: str, paragraph_sentences: int) -> str:
    if not text or not text.strip():
        return ""

    try:
        from deepmultilingualpunctuation import PunctuationModel
    except ImportError as e:
        raise RuntimeError(
            "reformat model='full' requires deepmultilingualpunctuation. "
            "Install with: pip install deepmultilingualpunctuation nltk"
        ) from e

    restored = PunctuationModel().restore_punctuation(_WS_RE.sub(" ", text).strip())

    try:
        import nltk
        sentences = nltk.sent_tokenize(restored)
    except Exception:
        sentences = [s.strip() for s in _SENT_SPLIT_RE.split(restored) if s.strip()]

    sentences = [_capitalize_full(s) for s in sentences if s.strip()]

    try:
        from nltk.tokenize.texttiling import TextTilingTokenizer
        tt = TextTilingTokenizer()
        blocks = tt.tokenize("\n\n".join(sentences))
        return "\n\n".join(b.strip() for b in blocks if b.strip())
    except Exception:
        return _paragraphize(sentences, paragraph_sentences)


def _capitalize_full(sentence: str) -> str:
    s = sentence.strip()
    if not s:
        return s
    s = s[0].upper() + s[1:]
    s = re.sub(r"\bi\b", "I", s)
    s = re.sub(r"\bi'(m|ve|ll|d)\b", lambda m: "I'" + m.group(1), s)
    return s


def _paragraphize(sentences: list[str], n: int) -> str:
    if n <= 0:
        n = 1
    paragraphs = [
        " ".join(sentences[i : i + n]) for i in range(0, len(sentences), n)
    ]
    return "\n\n".join(paragraphs)
