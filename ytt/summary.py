"""Summary section: an offline extractive fallback, plus in-place replacement.

The script cannot write a real (abstractive) summary on its own; it has no
LLM. It writes a short extractive one between markers, and an agent (or a
person) can later swap in a written summary with `add_summary.py`, which
rewrites the Markdown and HTML siblings in place without refetching anything.
"""

from __future__ import annotations

import html
import math
import re
from collections import Counter
from pathlib import Path

from .models import Paragraph

MD_START = "<!-- yt-summary:start -->"
MD_END = "<!-- yt-summary:end -->"

_STOP = set(
    """a about above after again against all am an and any are as at be because been before being below
    between both but by can could did do does doing down during each few for from further had has have having
    he her here hers herself him himself his how i if in into is it its itself just let me more most my myself
    no nor not now of off on once only or other our ours ourselves out over own really right same she should so
    some such than that the their theirs them themselves then there these they this those through to too under
    until up very was we were what when where which while who whom why will with would you your yours yourself
    yourselves okay ok yeah like gonna going get got go know mean thing things um uh actually basically little
    lot kind sort pretty also well one see look guys way want make just""".split()
)
_WORD = re.compile(r"[a-z][a-z0-9'+#.-]*[a-z0-9+#]|[a-z]")
_SENT = re.compile(r"(?<=[.!?])\s+")


def extractive(paragraphs: list[Paragraph], n: int = 5) -> list[tuple[float, str]]:
    """Pick the n most content-dense sentences (TF-IDF over paragraphs), in time order."""
    sents: list[tuple[float, str, list[str]]] = []
    for p in paragraphs:
        if p.is_cue:
            continue
        for s in _SENT.split(p.text):
            words = [w for w in _WORD.findall(s.lower()) if w not in _STOP and len(w) > 2]
            if 6 <= len(s.split()) <= 45 and len(words) >= 3:
                sents.append((p.start, s.strip(), words))
    if not sents or n <= 0:
        return []
    df = Counter(w for _, _, ws in sents for w in set(ws))
    tf = Counter(w for _, _, ws in sents for w in ws)
    total = len(sents)

    def score(ws: list[str]) -> float:
        return sum(math.log(1 + tf[w]) * math.log(1 + total / df[w]) for w in set(ws)) / (len(ws) ** 0.5)

    ranked = sorted(range(len(sents)), key=lambda i: score(sents[i][2]), reverse=True)
    # Spread picks across the video rather than clustering in one section.
    chosen: list[int] = []
    min_gap = max(1, total // (n * 2))
    for i in ranked:
        if all(abs(i - j) >= min_gap for j in chosen):
            chosen.append(i)
        if len(chosen) >= n:
            break
    return [(sents[i][0], sents[i][1]) for i in sorted(chosen)]


# --------------------------------------------------------------------------- md -> html (subset)


def _inline(s: str) -> str:
    s = html.escape(s)  # quote=True: link targets end up inside href="..."
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"(?<![*\w])\*([^*\n]+)\*(?![*\w])", r"<em>\1</em>", s)
    s = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", r'<a href="\2">\1</a>', s)
    s = re.sub(r"&lt;(https?://[^\s&<>]+(?:&amp;[^\s&<>]+)*)&gt;", r'<a href="\1">\1</a>', s)  # <https://...> autolinks
    return s


def md_to_html(md: str) -> str:
    """Enough Markdown for a summary: headings, bullets, numbers, quotes, paragraphs."""
    out: list[str] = []
    list_tag: str | None = None
    para: list[str] = []

    def close_para() -> None:
        if para:
            out.append("<p>" + _inline(" ".join(para)) + "</p>")
            para.clear()

    def close_list() -> None:
        nonlocal list_tag
        if list_tag:
            out.append(f"</{list_tag}>")
            list_tag = None

    for raw in md.splitlines():
        line = raw.rstrip()
        if not line.strip() or line.strip().startswith("<!--"):
            close_para()
            close_list()
            continue
        m = re.match(r"^(#{1,6})\s+(.*)", line)
        if m:
            close_para()
            close_list()
            lvl = min(6, len(m.group(1)) + 2)  # nested under the page's h2
            out.append(f"<h{lvl}>{_inline(m.group(2))}</h{lvl}>")
            continue
        m = re.match(r"^\s*(?:[-*+]|(\d+)[.)])\s+(.*)", line)
        if m:
            close_para()
            tag = "ol" if m.group(1) else "ul"
            if list_tag != tag:
                close_list()
                out.append(f"<{tag}>")
                list_tag = tag
            out.append(f"<li>{_inline(m.group(2))}</li>")
            continue
        if line.lstrip().startswith(">"):
            close_para()
            close_list()
            out.append(f"<blockquote>{_inline(line.lstrip()[1:].strip())}</blockquote>")
            continue
        close_list()
        para.append(line.strip())
    close_para()
    close_list()
    return "\n".join(out)


# --------------------------------------------------------------------------- replace in place

HTML_START = "<!--yt-summary:start-->"
HTML_END = "<!--yt-summary:end-->"


def _replace_between(text: str, start: str, end: str, new: str) -> str:
    i, j = text.find(start), text.find(end)
    if i < 0 or j < i:
        raise ValueError(f"summary markers {start} ... {end} not found")
    return text[: i + len(start)] + "\n" + new.strip() + "\n" + text[j:]


def inject(md_path: Path, summary_md: str) -> list[Path]:
    """Replace the summary in the .md file and any sibling .html. Returns files changed."""
    changed = []
    md_text = md_path.read_text(encoding="utf-8")
    md_path.write_text(_replace_between(md_text, MD_START, MD_END, summary_md), encoding="utf-8")
    changed.append(md_path)
    html_path = md_path.with_suffix(".html")
    if html_path.exists():
        h = html_path.read_text(encoding="utf-8")
        html_path.write_text(_replace_between(h, HTML_START, HTML_END, md_to_html(summary_md)), encoding="utf-8")
        changed.append(html_path)
    txt_path = md_path.with_suffix(".txt")
    if txt_path.exists():
        t = txt_path.read_text(encoding="utf-8")
        try:
            txt_path.write_text(_replace_between(t, "[summary]", "[/summary]", summary_md), encoding="utf-8")
            changed.append(txt_path)
        except ValueError:
            pass
    return changed
