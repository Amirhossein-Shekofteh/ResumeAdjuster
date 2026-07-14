from __future__ import annotations

import re

# Common resume section names we're willing to promote to Markdown `##`
# headings when the source text has no heading syntax at all. Kept
# deliberately narrow and curated -- a generic "any short standalone line is
# a header" heuristic produces too many false positives on real resumes
# (e.g. a one-line job title or company name would get promoted too).
_KNOWN_SECTION_HEADINGS = {
    "summary",
    "objective",
    "education",
    "experience",
    "work experience",
    "professional experience",
    "skills",
    "technical skills",
    "projects",
    "certifications",
    "awards",
    "honors",
    "honors and awards",
    "campus involvement",
    "extracurricular activities",
    "publications",
    "volunteer experience",
    "leadership",
    "languages",
    "interests",
    "references",
    "activities",
    "coursework",
    "relevant coursework",
}

_BULLET_PATTERN = re.compile(r"^(\s*)[•*-]\s+")


def _has_markdown_headings(text: str) -> bool:
    return any(line.lstrip().startswith("#") for line in text.splitlines())


def _normalize_bullets(text: str) -> str:
    """
    Normalize `•`, `*`, and `-` bullet markers to a consistent `- ` prefix.

    pandoc only recognizes a bullet list when every item in a block uses the
    same marker; resumes copy-pasted from Word/PDF often mix `•` characters
    with `-`/`*`, which Markdown may not parse as a single list at all.
    """

    lines = text.splitlines()
    normalized = [_BULLET_PATTERN.sub(r"\1- ", line) for line in lines]
    return "\n".join(normalized)


def _ensure_blank_line_before_bullets(text: str) -> str:
    """
    Insert a blank line before a bullet block that immediately follows
    non-blank, non-bullet text.

    Markdown parsers (pandoc's and the CommonMark-based renderer Streamlit
    uses) require a blank line to separate a paragraph from a following
    list. Without it, dash-prefixed lines right after a paragraph (e.g. a
    job title/date line immediately followed by bullets, with no blank line
    in between) are treated as a lazy continuation of that paragraph and
    rendered as run-on text joined by " - " instead of an actual bulleted
    list.
    """

    lines = text.splitlines()
    result: list[str] = []

    for line in lines:
        is_bullet = bool(_BULLET_PATTERN.match(line))
        previous = result[-1] if result else ""

        if is_bullet and previous.strip() and not _BULLET_PATTERN.match(previous):
            result.append("")

        result.append(line)

    return "\n".join(result)


def normalize_resume_markdown(text: str) -> str:
    """
    Make sure resume text has real Markdown heading/bullet syntax before it
    reaches pandoc or `st.markdown()`.

    Raw uploads (txt/pdf/docx) and the deterministic "keep unchanged" agent
    output are plain text with no `#`/`##` headings at all -- pandoc has
    nothing to convert into LaTeX `\\section`/`\\subsection` commands, so
    section styling and spacing in the LaTeX template never fires. This
    normalizer is applied only at the display/export boundary, never fed
    back into agent/checker inputs: `src/checks/resume_revision_checker.py`
    requires `evidence_source` to be an exact substring of the raw resume
    text, so normalizing that text before it reaches the agents would
    silently break grounding checks.
    """

    text = text.strip()

    if not text:
        return text

    if _has_markdown_headings(text):
        return _ensure_blank_line_before_bullets(_normalize_bullets(text))

    lines = text.splitlines()
    promoted: list[str] = []
    title_promoted = False

    for line in lines:
        stripped = line.strip()

        if not stripped:
            promoted.append(line)
            continue

        if not title_promoted:
            promoted.append(f"# {stripped}")
            title_promoted = True
            continue

        if stripped.lower() in _KNOWN_SECTION_HEADINGS:
            promoted.append(f"## {stripped}")
            continue

        promoted.append(line)

    normalized = _normalize_bullets("\n".join(promoted))
    return _ensure_blank_line_before_bullets(normalized)


def extract_resume_title(text: str) -> tuple[str | None, str]:
    """
    Split a leading level-1 Markdown heading (the resume owner's name) off
    normalized resume text, returning (title, remaining_body).

    Used only by the PDF export path. Our LaTeX template renders section
    names (level-2 headings) with a prominent colored rule via `\\section`,
    and document_export.py shifts heading levels by -1 so those sections
    map to `\\section` instead of the less prominent `\\subsection`. That
    shift only makes sense once the level-1 title line is out of the body --
    otherwise it would be shifted to an invalid level-0 heading. The title
    is rendered separately via pandoc `--metadata title=...` and a plain
    centered title block in the template, matching how real resumes present
    a name (not as a ruled section header).
    """

    lines = text.splitlines()

    if not lines or not lines[0].startswith("# "):
        return None, text

    title = lines[0][2:].strip()
    rest = "\n".join(lines[1:]).lstrip("\n")

    return (title or None), rest
