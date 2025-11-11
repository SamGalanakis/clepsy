import pytest

from clepsy.modules.aggregator.desktop_source.worker import prepare_ocr_text


def test_prepare_ocr_text_normalizes_and_deduplicates_lines():
    raw_text = "Hello   world\nHello   world\n  hi \n--\nabc"

    result = prepare_ocr_text(raw_text, max_words=10, max_chars=100)

    assert result == "Hello world\nabc"


def test_prepare_ocr_text_strips_non_ascii_and_short_lines():
    raw_text = "★彡Test彡★\n??\nab\n12345\nnormal line"

    result = prepare_ocr_text(raw_text, max_words=10, max_chars=100)

    lines = result.splitlines()
    assert "normal line" in lines
    assert "Shan TestShan" in lines
    assert all(ord(ch) < 128 for ch in result)


def test_prepare_ocr_text_drops_numeric_telemetry():
    raw_text = "CPU 95%\n1234567890\n0001\nFrame 120 FPS\nalpha"

    result = prepare_ocr_text(raw_text, max_words=10, max_chars=100)

    assert result == "CPU 95%\nFrame 120 FPS\nalpha"


def test_prepare_ocr_text_applies_word_and_char_limits():
    raw_text = "one two three four five six seven eight nine ten eleven twelve"

    result = prepare_ocr_text(raw_text, max_words=5, max_chars=20)

    assert result == "one two three four"


@pytest.mark.parametrize("input_text", ["", "  ", "--", "??", "ab"])
def test_prepare_ocr_text_handles_empty_results(input_text):
    assert prepare_ocr_text(input_text) == ""
