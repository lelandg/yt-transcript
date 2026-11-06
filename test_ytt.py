"""Offline tests for the ytt package (no network)."""

from pathlib import Path

import pytest

import yt_transcript
from ytt import fetch, paths, render, shots, summary, text
from ytt.models import Chapter, Paragraph, Segment, Shot, VideoData, fmt_time, parse_time


def seg(start, text, dur=2.0):
    return Segment(start, dur, text)


# --------------------------------------------------------------------------- models


@pytest.mark.parametrize("v,want", [("90", 90), ("1:30", 90), ("01:02:03", 3723), ("1m30s", 90), ("2h", 7200), ("12.5", 12.5)])
def test_parse_time(v, want):
    assert parse_time(v) == want


def test_parse_time_rejects_garbage():
    with pytest.raises(ValueError):
        parse_time("abc")


def test_fmt_time():
    assert fmt_time(5) == "00:05"
    assert fmt_time(3723) == "1:02:03"


@pytest.mark.parametrize(
    "url",
    [
        "https://www.youtube.com/watch?v=rCiLORb2QbY",
        "https://youtu.be/rCiLORb2QbY?t=3",
        "https://www.youtube.com/shorts/rCiLORb2QbY",
        "https://www.youtube.com/embed/rCiLORb2QbY",
        "https://www.youtube.com/live/rCiLORb2QbY",
        "rCiLORb2QbY",
    ],
)
def test_extract_video_id(url):
    assert fetch.extract_video_id(url) == "rCiLORb2QbY"


def test_extract_video_id_bad():
    with pytest.raises(ValueError):
        fetch.extract_video_id("not a video")


def test_videodata_roundtrip():
    d = VideoData("abcdefghijk", "u", "T", chapters=[Chapter(0, 5, "a")], segments=[seg(0, "hi")])
    assert VideoData.from_dict(d.to_dict()) == d


# --------------------------------------------------------------------------- text


def test_tokenize_drops_inline_cues_and_marks_speakers():
    items = text.tokenize([seg(0, "all stock [music]"), seg(2, ">> Okay, next"), seg(4, ">> [music]")])
    words = [i for i in items if isinstance(i, text.Word)]
    assert [w.text for w in words] == ["all", "stock", "Okay,", "next"]
    assert words[2].speaker_change
    cues = [i for i in items if not isinstance(i, text.Word)]
    assert len(cues) == 1 and cues[0].label == "[music]"


def test_word_times_interpolate_within_segment():
    words = [i for i in text.tokenize([seg(10, "a b c d", dur=4)]) if isinstance(i, text.Word)]
    assert [w.time for w in words] == [10, 11, 12, 13]


def test_punctuated_paragraphs_keep_sentences_whole():
    segs = [seg(0, "Okay, for this review, I'm using"), seg(2, "my bread bin, all stock [music]"), seg(4, "components. So, let's go.")]
    paras = text.build_paragraphs(segs)
    assert len(paras) == 1
    assert "all stock components." in paras[0].text
    assert "[music]" not in paras[0].text


def test_paragraphs_break_at_chapters_and_carry_times():
    segs = [seg(0, "First thing here."), seg(3, "More words now."), seg(10, "Second chapter text.")]
    paras = text.build_paragraphs(segs, [Chapter(0, 10, "A"), Chapter(10, 20, "B")])
    assert [p.chapter for p in paras] == [0, 1]
    assert paras[1].start == 10


def test_unpunctuated_captions_get_sentences():
    words = " ".join(f"word{i}" for i in range(60))
    paras = text.build_paragraphs([seg(0, words, dur=30)])
    joined = " ".join(p.text for p in paras)
    assert joined.count(".") >= 2
    assert joined[0].isupper()


def test_sentences_per_paragraph():
    segs = [seg(i * 2, f"Sentence number {i}.") for i in range(9)]
    paras = text.build_paragraphs(segs, sentences_per_paragraph=3)
    assert len(paras) == 3


def test_leading_music_cue_kept_once():
    paras = text.build_paragraphs([seg(0, "[music]"), seg(1, "[music]"), seg(3, "Hello there.")])
    assert paras[0].is_cue and paras[0].text == "[music]"
    assert sum(p.is_cue for p in paras) == 1


# --------------------------------------------------------------------------- paths


def test_sanitize_filename():
    assert paths.sanitize_filename("New OS for the C64? #commodore64 #retro") == "New OS for the C64"
    assert paths.sanitize_filename('a<b>c:"d"/e') == "abcde"
    assert paths.sanitize_filename("CON") == "CON_"
    assert paths.sanitize_filename("   ") == "transcript"


def test_output_dir_explicit(tmp_path):
    d, why = paths.resolve_output_dir(str(tmp_path / "x"), None)
    assert d == (tmp_path / "x").resolve() and why == "--directory"


def test_output_dir_uses_repo_root(tmp_path):
    (tmp_path / ".git").mkdir()
    sub = tmp_path / "src" / "deep"
    sub.mkdir(parents=True)
    d, _ = paths.resolve_output_dir(None, str(sub))
    assert d == tmp_path.resolve() / "Notes"


def test_output_dir_plain_folder_and_existing_lowercase(tmp_path):
    work = tmp_path / "work"
    (work / "notes").mkdir(parents=True)
    d, why = paths.resolve_output_dir(None, str(work))
    assert d.name == "notes" and "working folder" in why


def test_output_dir_falls_back_without_a_folder():
    d, why = paths.resolve_output_dir(None, str(Path.home()))
    assert d.parent == paths.TOOL_HOME and "no working folder" in why


# --------------------------------------------------------------------------- summary


def test_extractive_summary_is_ordered_and_bounded():
    paras = [
        Paragraph(i * 10, i * 10 + 5, f"The Commodore {i} computer runs a graphical operating system with windows and menus number {i}.")
        for i in range(20)
    ]
    out = summary.extractive(paras, 4)
    assert 1 <= len(out) <= 4
    assert [t for t, _ in out] == sorted(t for t, _ in out)


def test_md_to_html_subset():
    h = summary.md_to_html("**TL;DR** it works\n\n- one `x`\n- two [link](https://a.b)\n\n1. first")
    assert "<strong>TL;DR</strong>" in h and "<ul>" in h and "<code>x</code>" in h
    assert '<a href="https://a.b">link</a>' in h and "<ol>" in h


def test_md_to_html_escapes():
    assert "&lt;script&gt;" in summary.md_to_html("<script>alert(1)</script>")


def _sample():
    data = VideoData("abcdefghijk", "https://www.youtube.com/watch?v=abcdefghijk", "Title #tag",
                     chapters=[Chapter(0, 30, "Intro"), Chapter(30, 60, "Body")], duration=60)
    paras = [Paragraph(0, 10, "Hello world.", 0), Paragraph(31, 40, "In the body.", 1)]
    return data, paras


def test_inject_updates_md_and_html(tmp_path):
    data, paras = _sample()
    md = tmp_path / "n.md"
    md.write_text(render.render_md(data, paras, [], "auto"), encoding="utf-8")
    md.with_suffix(".html").write_text(render.render_html(data, paras, [], "auto", tmp_path), encoding="utf-8")
    changed = summary.inject(md, "**Written** summary")
    assert len(changed) == 2
    assert "**Written** summary" in md.read_text(encoding="utf-8")
    assert "<strong>Written</strong>" in md.with_suffix(".html").read_text(encoding="utf-8")


def test_regeneration_keeps_written_summary(tmp_path):
    data, paras = _sample()
    md = tmp_path / "n.md"
    md.write_text(render.render_md(data, paras, [], "My own words."), encoding="utf-8")
    assert yt_transcript._existing_written_summary(md, data.video_id) == "My own words."
    auto = render.summary_block_md([(0, "x")], data, None)
    md.write_text(render.render_md(data, paras, [], auto), encoding="utf-8")
    assert yt_transcript._existing_written_summary(md, data.video_id) is None


# --------------------------------------------------------------------------- render


def test_layout_places_shots_and_chapters():
    data, paras = _sample()
    sh = [Shot(32, "f/shot.jpg", ["Chapter: Body"])]
    kinds = [k for k, _ in render.layout(data, paras, sh)]
    assert kinds == ["chapter", "para", "chapter", "shot", "para"]


def test_render_md_and_html_content(tmp_path):
    data, paras = _sample()
    sh = [Shot(32, "Title_files/shot_00-32.jpg", ["Speaker cue: \"this slide\""])]
    md = render.render_md(data, paras, sh, "S")
    assert md.startswith("# Title\n")
    assert "[00:31](https://www.youtube.com/watch?v=abcdefghijk&t=31s)" in md
    assert "### 00:30 · Body" in md and "Title_files/shot_00-32.jpg" in md
    h = render.render_html(data, paras, sh, "S", tmp_path)
    assert "<title>Title</title>" in h and 'id="shot-32"' in h and summary.HTML_START in h


def test_render_txt_and_json():
    data, paras = _sample()
    assert "[summary]\nS\n[/summary]" in render.render_txt(data, paras, [], "S")
    assert '"summary_md": "S"' in render.render_json(data, paras, [], "S")


# --------------------------------------------------------------------------- shots


def test_cue_candidates_prefer_strong_phrases():
    c = shots.cue_candidates([seg(10, "as you can see here the menu"), seg(20, "nothing to note"), seg(30, "this slide shows it")])
    assert [x.time for x in c] == pytest.approx([10.5, 30.5])  # phrase time + settle delay
    assert all(x.score >= 3 for x in c)


def test_merge_sums_agreeing_signals_and_anchors_on_scene():
    m = shots.merge([shots.Candidate(10, 3, ["Chapter: A"]), shots.Candidate(13, 2, ["Scene"], is_scene=True), shots.Candidate(40, 1, ["x"])])
    assert len(m) == 2 and m[0].time == 13 and m[0].score == 5


def test_select_respects_gap_and_limit():
    cands = [shots.Candidate(t, s, []) for t, s in [(10, 5), (12, 4), (30, 3), (50, 2), (70, 1)]]
    picked = shots.select(cands, 3, min_gap=8, duration=100)
    assert sorted(c.time for c in picked) == [10, 30, 50]


def test_heatmap_peaks():
    hm = [{"start_time": i, "end_time": i + 1, "value": v} for i, v in enumerate([0.1, 0.9, 0.2, 0.3, 0.7, 0.1])]
    assert [round(c.time, 1) for c in shots.heatmap_candidates(hm)] == [1.5, 4.5]


def test_default_limit():
    assert shots.default_limit(120) == 6 and shots.default_limit(707) == 12 and shots.default_limit(7200) == 24


def test_shot_filename_is_portable():
    assert shots.shot_filename(3723) == "shot_1-02-03.jpg"


def test_md_to_html_autolinks():
    assert '<a href="https://github.com/x/y">https://github.com/x/y</a>' in summary.md_to_html("Repo: <https://github.com/x/y>.")


def test_noise_cues_dropped():
    paras = text.build_paragraphs([seg(0, "[clears throat]"), seg(1, "Hello there.")])
    assert not any(p.is_cue for p in paras)


def test_summary_links_cannot_break_out_of_href():
    h = summary.md_to_html('[x](https://h/"/onmouseover="alert(1))')
    assert 'onmouseover="' not in h and "&quot;" in h


def test_written_summary_not_carried_to_another_video(tmp_path):
    data, paras = _sample()
    md = tmp_path / "n.md"
    md.write_text(render.render_md(data, paras, [], "Words about video A."), encoding="utf-8")
    assert yt_transcript._existing_written_summary(md, "zzzzzzzzzzz") is None


def test_strip_note_suffix_keeps_dots():
    assert paths.strip_note_suffix("Talk v2.0") == "Talk v2.0"
    assert paths.strip_note_suffix("Talk v2.0.md") == "Talk v2.0"
    assert paths.sanitize_filename("CON.txt") == "CON.txt_"


def test_sentence_end_inside_brackets_and_ie():
    paras = text.build_paragraphs([seg(0, "He left (finally.) Then i.e. this works.")])
    assert "(finally.) " in paras[0].text and "(finally.)." not in paras[0].text
    assert "i.e." in paras[0].text


def test_first_line_handles_empty_messages():
    assert fetch.first_line(TimeoutError()) == "TimeoutError"
    assert fetch.first_line(ValueError("a\nb")) == "a"


def test_trailing_cue_emitted():
    paras = text.build_paragraphs([seg(0, "Hello there."), seg(5, "Goodbye now."), seg(9, "[applause]")])
    assert paras[-1].is_cue and paras[-1].text == "[applause]"


def test_long_unpunctuated_run_in_punctuated_captions_splits():
    body = " ".join(f"w{i}" for i in range(150))
    segs = [seg(0, "Short one. Another one. And a third. " + body, dur=60)]
    assert max(len(p.text.split()) for p in text.build_paragraphs(segs)) <= 130


def test_full_model_warns_when_unavailable(caplog, monkeypatch):
    monkeypatch.setattr(text, "restore_punctuation", lambda words: False)
    with caplog.at_level("WARNING", logger="yt_transcript"):
        text.build_paragraphs([seg(0, "hello there.")], model="full")
    assert "-m full did not run" in caplog.text


def test_raw_mode_keeps_chapters(tmp_path, monkeypatch):
    data = VideoData("abcdefghijk", "https://www.youtube.com/watch?v=abcdefghijk", "T",
                     chapters=[Chapter(0, 10, "A"), Chapter(10, 20, "B")], duration=20,
                     segments=[seg(1, "one"), seg(12, "two")])
    monkeypatch.setattr(fetch, "get_video", lambda *a, **k: data)
    assert yt_transcript.main(["abcdefghijk", "--raw", "-d", str(tmp_path), "-q"]) == 0
    md = (tmp_path / "T.md").read_text(encoding="utf-8")
    assert md.index("### 00:00 · A") < md.index("one") < md.index("### 00:10 · B") < md.index("two")


def test_rerun_refreshes_existing_siblings(tmp_path, monkeypatch):
    data = VideoData("abcdefghijk", "https://www.youtube.com/watch?v=abcdefghijk", "T", duration=20,
                     segments=[seg(1, "Hello there.")])
    monkeypatch.setattr(fetch, "get_video", lambda *a, **k: data)
    assert yt_transcript.main(["abcdefghijk", "--html", "-d", str(tmp_path), "-q"]) == 0
    html_file = tmp_path / "T.html"
    html_file.write_text("stale", encoding="utf-8")
    assert yt_transcript.main(["abcdefghijk", "-d", str(tmp_path), "-q"]) == 0
    assert html_file.read_text(encoding="utf-8").startswith("<!doctype html>")


def test_fetch_error_keeps_full_message(tmp_path, monkeypatch, caplog):
    def boom(*a, **k):
        raise RuntimeError("Could not retrieve a transcript\nYouTube is blocking requests from your IP")
    monkeypatch.setattr(fetch, "get_video", boom)
    with caplog.at_level("ERROR", logger="yt_transcript"):
        assert yt_transcript.main(["abcdefghijk", "-d", str(tmp_path), "-q"]) == 1
    assert "blocking requests from your IP" in caplog.text


# --------------------------------------------------------------------------- CodeRabbit retro review (PR #4)

import json as _json
import logging as _logging

import add_summary


def test_nested_autolink_inside_link_cannot_inject():
    h = summary.md_to_html('[a](https://x/<https://evil/" onmouseover="alert(1)>)')
    assert "onmouseover=\"" not in h
    assert h.count("<a ") <= 1
    # Without whitespace both patterns match; the old two-pass code nested an
    # anchor inside href here. One pass keeps the autolink as plain URL text.
    assert summary.md_to_html("[a](https://x/<https://evil/>)") == '<p><a href="https://x/&lt;https://evil/&gt;">a</a></p>'


def test_link_text_still_gets_emphasis_and_urls_do_not():
    h = summary.md_to_html("[**bold**](https://x/*a*) and <https://y/z>")
    assert '<a href="https://x/*a*"><strong>bold</strong></a>' in h
    assert '<a href="https://y/z">https://y/z</a>' in h


@pytest.mark.parametrize("bad", ["inf", "nan", "-5", "-1:00", "1e309"])
def test_parse_time_rejects_nonfinite_and_negative(bad):
    with pytest.raises(ValueError):
        parse_time(bad)


def test_other_videos_notes_are_never_overwritten(tmp_path, monkeypatch):
    a = VideoData("aaaaaaaaaaa", "https://www.youtube.com/watch?v=aaaaaaaaaaa", "Same Title", segments=[seg(0, "First video.")])
    b = VideoData("bbbbbbbbbbb", "https://www.youtube.com/watch?v=bbbbbbbbbbb", "Same Title", segments=[seg(0, "Second video.")])
    monkeypatch.setattr(fetch, "get_video", lambda vid, *a_, **k: a if vid == "aaaaaaaaaaa" else b)
    assert yt_transcript.main(["aaaaaaaaaaa", "-d", str(tmp_path), "-q"]) == 0
    assert yt_transcript.main(["bbbbbbbbbbb", "-d", str(tmp_path), "-q"]) == 0
    assert "First video." in (tmp_path / "Same Title.md").read_text(encoding="utf-8")
    assert "Second video." in (tmp_path / "Same Title [bbbbbbbbbbb].md").read_text(encoding="utf-8")
    # Re-running the first video still regenerates its own file in place.
    assert yt_transcript.main(["aaaaaaaaaaa", "-d", str(tmp_path), "-q"]) == 0
    assert not (tmp_path / "Same Title [aaaaaaaaaaa].md").exists()


def test_inject_is_all_or_nothing(tmp_path):
    data, paras = _sample()
    md = tmp_path / "n.md"
    md.write_text(render.render_md(data, paras, [], "auto"), encoding="utf-8")
    md.with_suffix(".html").write_text("<html>no markers</html>", encoding="utf-8")
    before = md.read_text(encoding="utf-8")
    with pytest.raises(ValueError):
        summary.inject(md, "New summary")
    assert md.read_text(encoding="utf-8") == before


def test_inject_skips_txt_without_markers(tmp_path, caplog):
    data, paras = _sample()
    md = tmp_path / "n.md"
    md.write_text(render.render_md(data, paras, [], "auto"), encoding="utf-8")
    md.with_suffix(".txt").write_text("plain text, no markers", encoding="utf-8")
    with caplog.at_level("WARNING", logger="yt_transcript"):
        changed = summary.inject(md, "New summary")
    assert changed == [md] and "Skipped n.txt" in caplog.text


def test_add_summary_refuses_corrupt_json_before_changing_anything(tmp_path):
    data, paras = _sample()
    md = tmp_path / "n.md"
    md.write_text(render.render_md(data, paras, [], "auto"), encoding="utf-8")
    md.with_suffix(".json").write_text("{not json", encoding="utf-8")
    s = tmp_path / "s.md"
    s.write_text("Written summary", encoding="utf-8")
    before = md.read_text(encoding="utf-8")
    assert add_summary.main([str(md), str(s)]) == 1
    assert md.read_text(encoding="utf-8") == before


def test_add_summary_updates_json(tmp_path):
    data, paras = _sample()
    md = tmp_path / "n.md"
    md.write_text(render.render_md(data, paras, [], "auto"), encoding="utf-8")
    md.with_suffix(".json").write_text(render.render_json(data, paras, [], "auto"), encoding="utf-8")
    s = tmp_path / "s.md"
    s.write_text("Written summary", encoding="utf-8")
    assert add_summary.main([str(md), str(s)]) == 0
    assert _json.loads(md.with_suffix(".json").read_text(encoding="utf-8"))["summary_md"] == "Written summary"
    assert not list(tmp_path.glob("*.tmp"))


def test_setup_logging_does_not_stack_handlers():
    caller = _logging.NullHandler()
    saved_level = yt_transcript.log.level
    yt_transcript.log.addHandler(caller)
    try:
        yt_transcript.setup_logging(False, True)
        n = len(yt_transcript.log.handlers)
        yt_transcript.setup_logging(False, True)
        assert len(yt_transcript.log.handlers) == n
        assert caller in yt_transcript.log.handlers
    finally:
        for h in [h for h in yt_transcript.log.handlers if getattr(h, "_ytt_owned", False)]:
            yt_transcript.log.removeHandler(h)
            h.close()
        yt_transcript.log.removeHandler(caller)
        yt_transcript.log.setLevel(saved_level)


def test_undecodable_note_is_an_ownership_conflict(tmp_path):
    md = tmp_path / "x.md"
    md.write_bytes(b"\xff\xfe\x00 not utf-8 v=abcdefghijk")
    assert yt_transcript._same_video(md, "abcdefghijk") is False


def test_leftover_siblings_without_md_count_as_taken(tmp_path):
    (tmp_path / "T_files").mkdir()
    assert yt_transcript._name_taken(tmp_path, "T", "abcdefghijk") is True
    assert yt_transcript._name_taken(tmp_path, "V", "abcdefghijk") is False


def test_sibling_ownership_comes_from_metadata_not_links(tmp_path):
    data, paras = _sample()  # video abcdefghijk
    other = VideoData("zzzzzzzzzzz", "https://www.youtube.com/watch?v=zzzzzzzzzzz", "Other", segments=[seg(0, "x")])
    # Another video's page whose summary links to abcdefghijk must not be claimed by it.
    linked = "See [this one](https://www.youtube.com/watch?v=abcdefghijk&t=5s)."
    plain = [Paragraph(0, 1, "Other video text.")]
    (tmp_path / "A.html").write_text(render.render_html(other, plain, [], linked, tmp_path), encoding="utf-8")
    (tmp_path / "A.txt").write_text(render.render_txt(other, plain, [], linked), encoding="utf-8")
    assert yt_transcript._name_taken(tmp_path, "A", "abcdefghijk") is True
    # Siblings whose metadata names this video stay reusable, in every format.
    (tmp_path / "B.html").write_text(render.render_html(data, paras, [], "s", tmp_path), encoding="utf-8")
    (tmp_path / "B.txt").write_text(render.render_txt(data, paras, [], "s"), encoding="utf-8")
    (tmp_path / "B.json").write_text(render.render_json(data, paras, [], "s"), encoding="utf-8")
    assert yt_transcript._name_taken(tmp_path, "B", "abcdefghijk") is False
    # Mixed owners: taken.
    (tmp_path / "B.json").write_text(render.render_json(other, plain, [], "s"), encoding="utf-8")
    assert yt_transcript._name_taken(tmp_path, "B", "abcdefghijk") is True


def test_write_atomic_keeps_permissions_and_follows_symlinks(tmp_path):
    import os
    import stat
    target = tmp_path / "real.md"
    target.write_text("old", encoding="utf-8")
    os.chmod(target, stat.S_IREAD | stat.S_IWRITE)
    before = stat.S_IMODE(target.stat().st_mode)
    summary.write_atomic(target, "new")
    assert stat.S_IMODE(target.stat().st_mode) == before
    link = tmp_path / "link.md"
    try:
        link.symlink_to(target)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks need developer mode or admin on Windows")
    summary.write_atomic(link, "via link")
    assert link.is_symlink() and target.read_text(encoding="utf-8") == "via link"


def test_add_summary_rejects_non_object_json(tmp_path):
    data, paras = _sample()
    md = tmp_path / "n.md"
    md.write_text(render.render_md(data, paras, [], "auto"), encoding="utf-8")
    md.with_suffix(".json").write_text("[1, 2]", encoding="utf-8")
    s = tmp_path / "s.md"
    s.write_text("Written", encoding="utf-8")
    before = md.read_text(encoding="utf-8")
    assert add_summary.main([str(md), str(s)]) == 1
    assert md.read_text(encoding="utf-8") == before


def test_write_atomic_uses_unique_temp_and_cleans_up(tmp_path, monkeypatch):
    target = tmp_path / "f.md"
    summary.write_atomic(target, "one")
    assert target.read_text(encoding="utf-8") == "one"

    def boom(*a, **k):
        raise OSError("disk full")
    monkeypatch.setattr(summary.os, "replace", boom)
    with pytest.raises(OSError):
        summary.write_atomic(target, "two")
    assert target.read_text(encoding="utf-8") == "one"
    assert [p.name for p in tmp_path.iterdir()] == ["f.md"]


def test_launcher_refuses_to_delete_a_preexisting_broken_venv(tmp_path, monkeypatch):
    import importlib.util
    spec = importlib.util.spec_from_file_location("ytt_run", Path(__file__).parent / ".claude/skills/yt-transcript/scripts/run.py")
    run = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(run)
    tag = {"win32": ".venv_windows", "darwin": ".venv_mac"}.get(run.sys.platform, ".venv_linux")
    broken = tmp_path / tag
    broken.mkdir()
    (broken / "keep.txt").write_text("someone's file", encoding="utf-8")
    with pytest.raises(SystemExit):
        run.ensure_venv(tmp_path)
    assert (broken / "keep.txt").exists()


def _fake_capture_env(monkeypatch, tmp_path):
    """Stub out the network and ffmpeg so capture() selection logic runs offline."""
    monkeypatch.setattr(shots, "ffmpeg_exe", lambda: "ffmpeg")
    video = tmp_path / "v.mp4"
    video.write_bytes(b"x")
    monkeypatch.setattr(shots, "download_video", lambda *a, **k: video)
    monkeypatch.setattr(shots, "scene_candidates", lambda *a, **k: [])
    counter = iter(range(10_000))

    def grab(ff, v, t, out, width=1280):
        out.write_bytes(b"jpg")
        return True

    monkeypatch.setattr(shots, "grab_frame", grab)
    # Every frame gets a very different hash, so nothing is deduplicated.
    monkeypatch.setattr(shots, "dhash", lambda ff, img, size=16: (next(counter) * 0x9E3779B97F4A7C15) % (1 << 256))


def test_requested_shots_do_not_use_the_auto_allowance(tmp_path, monkeypatch):
    _fake_capture_env(monkeypatch, tmp_path)
    data = VideoData("abcdefghijk", "u", "T", duration=600,
                     chapters=[Chapter(i * 60, i * 60 + 60, f"C{i}") for i in range(10)])
    got = shots.capture(data, tmp_path / "a", "a", mode="chapters", extra_times=[5.2, 5.7, 300], limit=3)
    requested = [s for s in got if "Requested" in s.reasons]
    assert len(requested) == 2  # 5.2 and 5.7 are one second -> one frame
    assert len(got) - len(requested) == 3


def test_max_shots_zero_keeps_only_requested(tmp_path, monkeypatch):
    _fake_capture_env(monkeypatch, tmp_path)
    data = VideoData("abcdefghijk", "u", "T", duration=600,
                     chapters=[Chapter(i * 60, i * 60 + 60, f"C{i}") for i in range(10)])
    got = shots.capture(data, tmp_path / "a", "a", mode="auto", extra_times=[42], limit=0)
    assert [s.time for s in got] == [42]


# --------------------------------------------------------------------------- Codex review of the retro fixes


def test_emphasis_spanning_a_link_still_works():
    h = summary.md_to_html("**See [the guide](https://example.com/a*b*) for details**")
    assert h == '<p><strong>See <a href="https://example.com/a*b*">the guide</a> for details</strong></p>'


def test_fallback_name_is_also_ownership_checked(tmp_path, monkeypatch):
    mk = lambda vid, line: VideoData(vid, f"https://www.youtube.com/watch?v={vid}", "Title", segments=[seg(0, line)])
    vids = {"aaaaaaaaaaa": mk("aaaaaaaaaaa", "Video A."), "bbbbbbbbbbb": mk("bbbbbbbbbbb", "Video B."),
            "ccccccccccc": mk("ccccccccccc", "Video C.")}
    monkeypatch.setattr(fetch, "get_video", lambda vid, *a, **k: vids[vid])
    assert yt_transcript.main(["aaaaaaaaaaa", "-d", str(tmp_path), "-q"]) == 0
    # C claims the name B would fall back to.
    assert yt_transcript.main(["ccccccccccc", "-d", str(tmp_path), "-q", "-o", "Title [bbbbbbbbbbb]"]) == 0
    assert yt_transcript.main(["bbbbbbbbbbb", "-d", str(tmp_path), "-q"]) == 0
    assert "Video C." in (tmp_path / "Title [bbbbbbbbbbb].md").read_text(encoding="utf-8")
    assert "Video B." in (tmp_path / "Title [bbbbbbbbbbb] 2.md").read_text(encoding="utf-8")


def test_requested_shot_keeps_its_fractional_time(tmp_path, monkeypatch):
    _fake_capture_env(monkeypatch, tmp_path)
    seen = []
    orig = shots.grab_frame
    monkeypatch.setattr(shots, "grab_frame", lambda ff, v, t, out, width=1280: (seen.append(t), orig(ff, v, t, out))[1])
    data = VideoData("abcdefghijk", "u", "T", duration=60)
    got = shots.capture(data, tmp_path / "a", "a", mode="chapters", extra_times=[12.9, 12.2], limit=0)
    assert seen == [12.9] and got[0].time == 12.9
