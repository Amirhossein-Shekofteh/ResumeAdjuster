from __future__ import annotations

import re
import unicodedata

from src.config import CONFIG


WHITESPACE_RE = re.compile(r"[ \t\f\v]+")
REPEATED_BLANK_LINES_RE = re.compile(r"\n{3,}")
CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
PAGE_MARKER_RE = re.compile(
    r"(?im)^\s*(page\s*)?\d+\s*(of\s*\d+)?\s*$"
)
PDF_HYPHENATED_LINE_BREAK_RE = re.compile(r"(\w)-\n(\w)")
BROKEN_WORD_SPACING_RE = re.compile(r"\b([A-Za-z])(?:\s+)(?=[A-Za-z]\b)")


class TextCleaningError(ValueError):
    """
    Raised when text input cannot be cleaned.
    """


def _ensure_text(text: str | None) -> str:
    """
    Validate and normalize nullable text input.
    """

    if text is None:
        return ""

    if not isinstance(text, str):
        raise TextCleaningError(f"Expected text to be str or None, got {type(text).__name__}.")

    return text


def normalize_unicode(text: str | None) -> str:
    """
    Normalize Unicode characters.

    This helps standardize characters copied from PDFs, Word files, and web pages.
    """

    text = _ensure_text(text)
    return unicodedata.normalize("NFKC", text)


def normalize_line_endings(text: str | None) -> str:
    """
    Convert Windows and old Mac line endings to Unix-style line endings.
    """

    text = _ensure_text(text)
    return text.replace("\r\n", "\n").replace("\r", "\n")


def remove_control_characters(text: str | None) -> str:
    """
    Remove invisible control characters that sometimes appear in extracted PDF text.
    """

    text = _ensure_text(text)
    return CONTROL_CHAR_RE.sub("", text)


def clean_pdf_artifacts(text: str | None) -> str:
    """
    Clean common artifacts from PDF text extraction.

    This is intentionally conservative. It avoids removing content that could be
    real resume data, such as dates, GPA values, phone numbers, or section titles.
    """

    text = _ensure_text(text)
    text = normalize_line_endings(text)

    # Join words split by PDF line extraction, such as "mach-\nine" -> "machine".
    text = PDF_HYPHENATED_LINE_BREAK_RE.sub(r"\1\2", text)

    # Remove obvious page labels. This is conservative and may leave some page
    # numbers in place rather than risk deleting resume content.
    lines = text.split("\n")
    cleaned_lines: list[str] = []

    for line in lines:
        stripped = line.strip()

        if re.fullmatch(r"(?i)page\s+\d+(\s+of\s+\d+)?", stripped):
            continue

        cleaned_lines.append(line)

    return "\n".join(cleaned_lines)


def strip_trailing_spaces(text: str | None) -> str:
    """
    Remove leading/trailing spaces from each line while preserving line breaks.
    """

    text = _ensure_text(text)
    return "\n".join(line.strip() for line in text.split("\n"))


def normalize_whitespace(text: str | None) -> str:
    """
    Normalize repeated spaces and tabs while preserving line structure.

    This keeps resume sections readable instead of collapsing the entire document
    into one paragraph.
    """

    text = _ensure_text(text)
    text = text.replace("\u00a0", " ")
    text = WHITESPACE_RE.sub(" ", text)
    return strip_trailing_spaces(text)


def remove_repeated_blank_lines(text: str | None, max_blank_lines: int = 1) -> str:
    """
    Collapse repeated blank lines.

    max_blank_lines=1 means there can be at most one empty line between blocks.
    """

    text = _ensure_text(text)

    if max_blank_lines < 0:
        raise TextCleaningError("max_blank_lines must be 0 or greater.")

    if max_blank_lines == 0:
        return re.sub(r"\n+", "\n", text).strip()

    pattern = r"\n{" + str(max_blank_lines + 2) + r",}"
    replacement = "\n" * (max_blank_lines + 1)
    return re.sub(pattern, replacement, text).strip()


def trim_text(text: str | None, max_length: int | None = None) -> str:
    """
    Trim text to the configured maximum input length.

    This protects the app from sending very large documents to the model.
    """

    text = _ensure_text(text)
    limit = CONFIG.max_input_text_length if max_length is None else max_length

    if limit <= 0:
        raise TextCleaningError("max_length must be greater than 0.")

    text = text.strip()

    if len(text) <= limit:
        return text

    suffix = "\n\n[Text trimmed because it exceeded the maximum allowed length.]"
    available_length = max(limit - len(suffix), 0)

    return text[:available_length].rstrip() + suffix


def clean_text(text: str | None, max_length: int | None = None) -> str:
    """
    Main text-cleaning function used across the project.

    Use this for resumes, job descriptions, and coursework/student background text.
    """

    text = _ensure_text(text)

    text = normalize_unicode(text)
    text = normalize_line_endings(text)
    text = remove_control_characters(text)
    text = clean_pdf_artifacts(text)
    text = normalize_whitespace(text)
    text = remove_repeated_blank_lines(text)
    text = trim_text(text, max_length=max_length)

    return text


def clean_resume_text(text: str | None, max_length: int | None = None) -> str:
    """
    Clean resume text.

    Kept as a separate function so resume-specific rules can be added later.
    """

    return clean_text(text, max_length=max_length)


def clean_job_description_text(text: str | None, max_length: int | None = None) -> str:
    """
    Clean job description text.

    Kept as a separate function so job-description-specific rules can be added later.
    """

    return clean_text(text, max_length=max_length)


def clean_coursework_text(text: str | None, max_length: int | None = None) -> str:
    """
    Clean coursework and student background information.

    Kept as a separate function so coursework-specific rules can be added later.
    """

    return clean_text(text, max_length=max_length)