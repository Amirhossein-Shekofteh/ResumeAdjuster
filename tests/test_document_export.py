from __future__ import annotations

import io
import re
import shutil
import zipfile
from unittest.mock import patch

import pytest

from src.document_export import (
    DocumentExportError,
    render_resume_docx,
    render_resume_pdf,
)


def _patch_which_present():
    """Pretend both pandoc and tectonic are installed, regardless of the real PATH."""

    return patch("src.document_export.shutil.which", return_value="/usr/bin/fake")


def test_render_resume_pdf_calls_pandoc_with_template_and_tectonic() -> None:
    def fake_convert(text, to, format, outputfile, extra_args):
        with open(outputfile, "wb") as handle:
            handle.write(b"%PDF-fake")

    with _patch_which_present(), patch(
        "src.document_export.pypandoc.convert_text", side_effect=fake_convert
    ) as mock_convert:
        pdf_bytes = render_resume_pdf("# Resume\n\n## Skills\n\n- Python")

    assert pdf_bytes.startswith(b"%PDF-")

    _, kwargs = mock_convert.call_args
    assert kwargs["to"] == "pdf"
    assert "--pdf-engine=tectonic" in kwargs["extra_args"]
    assert "--template" in kwargs["extra_args"]


def test_render_resume_docx_calls_pandoc() -> None:
    def fake_convert(text, to, format, outputfile, extra_args):
        with open(outputfile, "wb") as handle:
            handle.write(b"PK\x03\x04fake")

    with _patch_which_present(), patch(
        "src.document_export.pypandoc.convert_text", side_effect=fake_convert
    ) as mock_convert:
        docx_bytes = render_resume_docx("# Resume")

    assert docx_bytes.startswith(b"PK\x03\x04")

    _, kwargs = mock_convert.call_args
    assert kwargs["to"] == "docx"


def test_render_resume_pdf_wraps_pandoc_failure() -> None:
    with _patch_which_present(), patch(
        "src.document_export.pypandoc.convert_text",
        side_effect=RuntimeError("pandoc exploded"),
    ):
        with pytest.raises(DocumentExportError, match="pandoc exploded"):
            render_resume_pdf("# Resume")


def test_render_resume_pdf_raises_friendly_error_when_tectonic_missing() -> None:
    with patch(
        "src.document_export.shutil.which",
        side_effect=lambda name: "/usr/bin/pandoc" if name == "pandoc" else None,
    ):
        with pytest.raises(DocumentExportError, match="requires tectonic"):
            render_resume_pdf("# Resume")


def test_render_resume_pdf_normalizes_headingless_markdown_before_pandoc() -> None:
    """Confirms normalize_resume_markdown is actually wired into export."""

    received: dict[str, str] = {}

    def fake_convert(text, to, format, outputfile, extra_args):
        received["text"] = text
        with open(outputfile, "wb") as handle:
            handle.write(b"%PDF-fake")

    with _patch_which_present(), patch(
        "src.document_export.pypandoc.convert_text", side_effect=fake_convert
    ):
        render_resume_pdf("Jordan Lee\n\nSkills\n- Python\n- SQL")

    # The name was pulled out as a title (not left in the body as a heading),
    # and the section heading survives (post heading-level shift it's what
    # pandoc will map to \section).
    assert "Jordan Lee" not in received["text"]
    assert "## Skills" in received["text"]


def test_render_resume_pdf_shifts_heading_level_and_sets_title_metadata_when_title_present() -> None:
    def fake_convert(text, to, format, outputfile, extra_args):
        with open(outputfile, "wb") as handle:
            handle.write(b"%PDF-fake")

    with _patch_which_present(), patch(
        "src.document_export.pypandoc.convert_text", side_effect=fake_convert
    ) as mock_convert:
        render_resume_pdf("# Jordan Lee\n\n## Skills\n\n- Python")

    _, kwargs = mock_convert.call_args
    extra_args = kwargs["extra_args"]

    assert "--shift-heading-level-by=-1" in extra_args
    assert "--metadata" in extra_args
    assert "title=Jordan Lee" in extra_args


def test_render_resume_pdf_skips_shift_and_metadata_when_no_title_found() -> None:
    def fake_convert(text, to, format, outputfile, extra_args):
        with open(outputfile, "wb") as handle:
            handle.write(b"%PDF-fake")

    with _patch_which_present(), patch(
        "src.document_export.pypandoc.convert_text", side_effect=fake_convert
    ) as mock_convert:
        render_resume_pdf("## Skills\n\n- Python")

    _, kwargs = mock_convert.call_args
    extra_args = kwargs["extra_args"]

    assert "--shift-heading-level-by=-1" not in extra_args
    assert "--metadata" not in extra_args


def test_render_resume_docx_does_not_shift_heading_level_or_set_title() -> None:
    def fake_convert(text, to, format, outputfile, extra_args):
        with open(outputfile, "wb") as handle:
            handle.write(b"PK\x03\x04fake")

    with _patch_which_present(), patch(
        "src.document_export.pypandoc.convert_text", side_effect=fake_convert
    ) as mock_convert:
        render_resume_docx("# Jordan Lee\n\n## Skills\n\n- Python")

    _, kwargs = mock_convert.call_args
    extra_args = kwargs["extra_args"]

    assert "--shift-heading-level-by=-1" not in extra_args
    assert "--metadata" not in extra_args


@pytest.mark.skipif(
    not (shutil.which("pandoc") and shutil.which("tectonic")),
    reason="pandoc/tectonic not installed in this environment",
)
def test_render_resume_pdf_end_to_end_produces_valid_pdf() -> None:
    pdf_bytes = render_resume_pdf("# Jordan Lee\n\n## Skills\n\n- Python\n- SQL")

    assert pdf_bytes[:5] == b"%PDF-"


@pytest.mark.skipif(
    not shutil.which("pandoc"),
    reason="pandoc not installed in this environment",
)
def test_render_resume_docx_end_to_end_produces_valid_docx() -> None:
    docx_bytes = render_resume_docx("# Jordan Lee\n\n## Skills\n\n- Python\n- SQL")

    assert docx_bytes[:4] == b"PK\x03\x04"


@pytest.mark.skipif(
    not shutil.which("pandoc"),
    reason="pandoc not installed in this environment",
)
def test_render_resume_docx_does_not_treat_leading_phone_number_as_a_list() -> None:
    """
    pandoc's default Markdown reader has `fancy_lists` on, which reads a
    leading parenthesized number (e.g. a phone number) as an ordered-list
    marker. Confirms the docx writer's actual output paragraph for that
    line has no list numbering -- not just that conversion succeeds.
    """

    docx_bytes = render_resume_docx(
        "# Jordan Lee\n\n"
        "(555) 123-4567 • jordan.lee@example.edu\n\n"
        "## Skills\n\n- Python\n- SQL"
    )

    with zipfile.ZipFile(io.BytesIO(docx_bytes)) as archive:
        document_xml = archive.read("word/document.xml").decode("utf-8")

    paragraphs = re.findall(r"<w:p\b.*?</w:p>", document_xml, re.S)
    phone_paragraph = next(p for p in paragraphs if "123-4567" in p)

    assert "<w:numPr>" not in phone_paragraph
