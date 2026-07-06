from __future__ import annotations

from src.text_cleaner import clean_text, remove_repeated_blank_lines, trim_text


def test_whitespace_cleanup() -> None:
    raw_text = "Hello     world\t\tfrom   ResumeAdjuster"
    cleaned = clean_text(raw_text)

    assert cleaned == "Hello world from ResumeAdjuster"


def test_blank_line_cleanup() -> None:
    raw_text = "Section A\n\n\n\nSection B\n\n\nSection C"
    cleaned = remove_repeated_blank_lines(raw_text)

    assert cleaned == "Section A\n\nSection B\n\nSection C"


def test_text_trimming() -> None:
    raw_text = "A" * 500
    trimmed = trim_text(raw_text, max_length=120)

    assert "[Text trimmed because it exceeded the maximum allowed length.]" in trimmed
    assert trimmed.startswith("A")