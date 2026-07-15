from __future__ import annotations

from src.resume_markdown import extract_resume_title, normalize_resume_markdown


def test_promotes_first_line_to_title_and_known_sections_to_headings() -> None:
    raw = (
        "Jordan Lee\n"
        "jordan.lee@example.edu\n"
        "\n"
        "Education\n"
        "B.S. in Data Science\n"
        "\n"
        "Skills\n"
        "- Python\n"
        "- SQL\n"
    )

    normalized = normalize_resume_markdown(raw)

    assert normalized.startswith("# Jordan Lee")
    assert "## Education" in normalized
    assert "## Skills" in normalized


def test_leaves_already_markdown_text_unchanged() -> None:
    raw = "# Jordan Lee\n\n## Skills\n\n- Python\n- SQL"

    assert normalize_resume_markdown(raw) == raw


def test_is_idempotent() -> None:
    raw = "Jordan Lee\n\nEducation\nB.S. in Data Science\n\nSkills\n- Python\n"

    once = normalize_resume_markdown(raw)
    twice = normalize_resume_markdown(once)

    assert once == twice


def test_does_not_promote_non_section_lines() -> None:
    raw = (
        "Jordan Lee\n"
        "Peer Tutor, Riverbend State University Math Center\n"
        "\n"
        "Skills\n"
        "- Python\n"
    )

    normalized = normalize_resume_markdown(raw)

    assert "## Peer Tutor" not in normalized
    assert "Peer Tutor, Riverbend State University Math Center" in normalized


def test_normalizes_bullet_markers() -> None:
    raw = "Skills\n* Python\n• SQL\n- Excel\n"

    normalized = normalize_resume_markdown(raw)

    assert "- Python" in normalized
    assert "- SQL" in normalized
    assert "- Excel" in normalized


def test_empty_input_returns_empty_string() -> None:
    assert normalize_resume_markdown("") == ""
    assert normalize_resume_markdown("   \n  ") == ""


def test_inserts_blank_line_before_bullets_glued_to_a_paragraph() -> None:
    """
    A bullet list with no blank line separating it from the preceding
    paragraph gets silently flattened into run-on text by Markdown parsers
    (pandoc and Streamlit's renderer alike) -- confirmed by actually running
    pandoc on this exact shape of input and inspecting the generated LaTeX.
    """

    raw = (
        "Jordan Lee\n"
        "\n"
        "Experience\n"
        "**Peer Tutor** \n"
        "2024-Present\n"
        "- Tutor undergraduate students.\n"
        "- Held weekly office hours.\n"
    )

    normalized = normalize_resume_markdown(raw)
    lines = normalized.splitlines()

    date_index = lines.index("2024-Present")
    assert lines[date_index + 1] == ""
    assert lines[date_index + 2] == "- Tutor undergraduate students."


def test_does_not_insert_blank_line_between_already_separated_bullets() -> None:
    raw = "# Jordan Lee\n\n## Skills\n\n- Python\n- SQL\n- Excel"

    assert normalize_resume_markdown(raw) == raw


def test_does_not_insert_blank_line_between_consecutive_bullets() -> None:
    raw = "Skills\n- Python\n- SQL\n- Excel\n"

    normalized = normalize_resume_markdown(raw)

    assert "- Python\n- SQL\n- Excel" in normalized


def test_adds_hard_line_break_before_label_lines() -> None:
    """
    Consecutive "Label: value" fact lines (degree, graduation date, GPA,
    coursework) with no blank line between them must not collapse into one
    run-on paragraph -- confirmed by actually rendering this exact shape
    through the LaTeX pipeline and inspecting the PDF.
    """

    raw = (
        "Jordan Lee\n"
        "\n"
        "Education\n"
        "B.S. in Data Science, Riverbend State University\n"
        "Expected Graduation: May 2027\n"
        "GPA: 3.6/4.0\n"
        "Relevant Coursework: Database Systems, Data Visualization\n"
    )

    normalized = normalize_resume_markdown(raw)
    lines = normalized.splitlines()

    degree_index = lines.index(
        "B.S. in Data Science, Riverbend State University  "
    )
    assert lines[degree_index + 1] == "Expected Graduation: May 2027  "
    assert lines[degree_index + 2] == "GPA: 3.6/4.0  "
    assert (
        lines[degree_index + 3]
        == "Relevant Coursework: Database Systems, Data Visualization"
    )


def test_does_not_split_a_hard_wrapped_prose_sentence() -> None:
    """
    Regression guard: an initial version of this heuristic added a break
    between ANY two adjacent plain lines, which incorrectly split ordinary
    prose that was merely word-wrapped in the source text (no Label: value
    pattern involved) into two visually separate lines instead of letting
    it flow/wrap naturally.
    """

    raw = (
        "Jordan Lee\n"
        "\n"
        "Summary\n"
        "Data Science student interested in an analytics role where I can "
        "apply my Python\n"
        "and statistics coursework to real business problems.\n"
    )

    normalized = normalize_resume_markdown(raw)

    assert "Python\nand statistics" in normalized
    assert "Python  \n" not in normalized


def test_label_line_hard_breaks_are_idempotent() -> None:
    raw = (
        "Jordan Lee\n"
        "\n"
        "Education\n"
        "B.S. in Data Science\n"
        "Expected Graduation: May 2027\n"
        "GPA: 3.6/4.0\n"
    )

    once = normalize_resume_markdown(raw)
    twice = normalize_resume_markdown(once)

    assert once == twice


def test_extract_resume_title_splits_leading_heading() -> None:
    text = "# Jordan Lee\n\n## Skills\n\n- Python"

    title, body = extract_resume_title(text)

    assert title == "Jordan Lee"
    assert body == "## Skills\n\n- Python"


def test_extract_resume_title_returns_none_when_no_leading_heading() -> None:
    text = "## Skills\n\n- Python"

    title, body = extract_resume_title(text)

    assert title is None
    assert body == text


def test_extract_resume_title_returns_none_for_empty_text() -> None:
    title, body = extract_resume_title("")

    assert title is None
    assert body == ""
