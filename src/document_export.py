from __future__ import annotations

import hashlib
import shutil
import tempfile
from pathlib import Path

import pypandoc

from src.resume_markdown import extract_resume_title, normalize_resume_markdown


class DocumentExportError(RuntimeError):
    """
    Raised when a resume document could not be exported to PDF or DOCX.
    """


_TEMPLATE_PATH = Path(__file__).resolve().parents[1] / "templates" / "resume_template.tex"


def _require_binary(binary_name: str) -> None:
    """
    Raise a clear error if a required system binary isn't on PATH.

    pandoc/tectonic failures otherwise surface as an opaque subprocess error deep
    inside pypandoc; checking up front lets us point the user at the fix.
    """

    if shutil.which(binary_name) is None:
        kind = "PDF" if binary_name == "tectonic" else "Document"
        raise DocumentExportError(
            f"{kind} export requires {binary_name}. Install it using the workshop "
            "prerequisite instructions."
        )


def _convert_markdown(
    markdown_text: str,
    to_format: str,
    extra_args: list[str] | None = None,
) -> bytes:
    """
    Convert resume Markdown to a binary document format using pandoc.

    pypandoc requires an `outputfile` for binary formats like pdf/docx, so we
    write to a temporary directory and read the bytes back.
    """

    _require_binary("pandoc")

    with tempfile.TemporaryDirectory() as tmp_dir:
        output_path = Path(tmp_dir) / f"resume.{to_format}"

        try:
            pypandoc.convert_text(
                markdown_text,
                to=to_format,
                format="md",
                outputfile=str(output_path),
                extra_args=extra_args or [],
            )
        except (RuntimeError, OSError) as exc:
            raise DocumentExportError(
                f"Could not generate {to_format.upper()} from the updated resume: {exc}"
            ) from exc

        return output_path.read_bytes()


def render_resume_pdf(markdown_text: str) -> bytes:
    """
    Typeset the resume Markdown into a PDF using the LaTeX resume template.

    The resume owner's name (a leading level-1 heading) is pulled out as a
    pandoc title and rendered as a plain centered title block, rather than
    left as a Markdown heading. Without this, pandoc maps level-1 -> \\section
    and level-2 -> \\subsection: the name would get the template's prominent
    colored-rule section styling while every real resume section (Education,
    Skills, Experience, ...) would get the template's much plainer subsection
    styling -- backwards from how a resume should look. Shifting the
    remaining heading levels by -1 makes every real section map to \\section
    uniformly. See src/resume_markdown.py's extract_resume_title docstring.
    """

    _require_binary("tectonic")

    normalized = normalize_resume_markdown(markdown_text)
    title, body = extract_resume_title(normalized)

    extra_args = [
        "--template",
        str(_TEMPLATE_PATH),
        "--pdf-engine=tectonic",
    ]

    if title:
        extra_args += ["--shift-heading-level-by=-1", "--metadata", f"title={title}"]

    return _convert_markdown(body, to_format="pdf", extra_args=extra_args)


def render_resume_docx(markdown_text: str) -> bytes:
    """
    Convert the resume Markdown into a Word (.docx) document.

    No title extraction or heading-level shift here: pandoc's built-in
    Markdown -> DOCX conversion maps heading levels straight to Word's own
    Heading 1/Heading 2 styles, which don't have the section/subsection
    styling mismatch the PDF template has, so the name-as-level-1-heading
    structure reads fine as-is.
    """

    normalized = normalize_resume_markdown(markdown_text)
    return _convert_markdown(normalized, to_format="docx")


def markdown_content_hash(markdown_text: str) -> str:
    """
    Stable hash used to cache generated documents per resume content.
    """

    return hashlib.sha256(markdown_text.encode("utf-8")).hexdigest()
