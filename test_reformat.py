"""Tests for the light backend of reformat.reformat.

Run with:
    python -m pytest test_reformat.py -v

The full backend is intentionally not tested here because it requires
downloading a ~500MB model from deepmultilingualpunctuation.
"""
import pytest

from reformat import reformat


def test_empty_string_returns_empty():
    assert reformat("") == ""


def test_punctuated_multi_sentence_capitalized_and_grouped():
    text = "this is one. this is two. this is three. this is four. this is five."
    result = reformat(text, model="light", paragraph_sentences=4)

    # Each sentence should start with a capital letter.
    assert "This is one." in result
    assert "This is two." in result
    assert "This is three." in result
    assert "This is four." in result
    assert "This is five." in result

    # 5 sentences with paragraph_sentences=4 should yield 2 paragraphs
    # separated by a blank line.
    paragraphs = [p for p in result.split("\n\n") if p.strip()]
    assert len(paragraphs) == 2


def test_unpunctuated_stream_is_split_and_capitalized():
    text = "so then we went to the store and then we bought some milk because we needed it"
    result = reformat(text, model="light", paragraph_sentences=4)

    # Should have been split into multiple sentences — count sentence terminators.
    terminators = sum(result.count(ch) for ch in ".!?")
    assert terminators >= 2, f"expected multiple sentences, got: {result!r}"

    # First character of the output should be capitalized.
    stripped = result.lstrip()
    assert stripped[:1].isupper(), f"output should start capitalized: {result!r}"


def test_paragraph_sentences_two_groups_by_twos():
    text = "one is here. two is here. three is here. four is here."
    result = reformat(text, model="light", paragraph_sentences=2)

    paragraphs = [p for p in result.split("\n\n") if p.strip()]
    assert len(paragraphs) == 2

    # Each paragraph should contain exactly 2 sentence terminators.
    for p in paragraphs:
        terminators = sum(p.count(ch) for ch in ".!?")
        assert terminators == 2, f"paragraph had {terminators} sentences: {p!r}"


def test_standalone_i_is_capitalized():
    result = reformat("i think i know", model="light")
    assert "I think I know" in result


def test_bracketed_cue_causes_paragraph_break_and_is_stripped():
    text = "hello world. [Music] this is after the cue."
    result = reformat(text, model="light", paragraph_sentences=10)

    # The literal bracketed cue should not appear in the output.
    assert "[Music]" not in result

    # It should cause a paragraph break — meaning a blank line separator.
    paragraphs = [p for p in result.split("\n\n") if p.strip()]
    assert len(paragraphs) >= 2, f"expected paragraph break at cue: {result!r}"

    # Both sides of the cue should be present and capitalized.
    assert "Hello world" in result
    assert "This is after the cue" in result


def test_bogus_model_raises_value_error():
    with pytest.raises(ValueError):
        reformat("hello world", model="bogus")
