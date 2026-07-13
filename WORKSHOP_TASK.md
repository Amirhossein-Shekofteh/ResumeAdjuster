# Workshop Task: "Updated Resume" Tab with LaTeX Preview + Word/PDF Download

## Goal

ResumeAdjuster already runs two agents (a gap analyst and a resume revision agent) and
produces a fully revised resume as **Markdown text**. Right now that text is only shown
on screen — there's no way to get a real, submittable document out of it.

In this task you'll add a **4th tab, "Updated Resume"**, that:

1. Shows the existing Markdown preview of the updated resume.
2. Lets the user click **Generate preview** to typeset that resume using **LaTeX**,
   producing a properly formatted document instead of plain text.
3. Shows an inline **PDF preview** of the typeset resume.
4. Offers two download buttons: **Word (.docx)** and **PDF**.

**Why this approach:** `pandoc` can convert Markdown straight into a compiled PDF by
combining it with a LaTeX *template* and a `--pdf-engine` — so we don't have to
hand-write a Markdown→LaTeX converter. The same `pandoc` call converts Markdown straight
to `.docx`. `tectonic` is the actual LaTeX engine that does the PDF compilation; it's a
single self-contained binary (no multi-gigabyte TeX Live install).

---

> **Before you start:** complete [WORKSHOP_PREREQUISITES.md](WORKSHOP_PREREQUISITES.md)
> first (Python, venv, `pip install -r requirements.txt`, and installing `pandoc` +
> `tectonic`). Everything below assumes that's already done.

---

## Step 1 — Add the LaTeX resume template

Create `templates/resume_template.tex` in the project root (new `templates/` folder):

```latex
\documentclass[10pt]{article}

\usepackage[margin=0.75in]{geometry}
\usepackage{titlesec}
\usepackage{enumitem}
\usepackage{hyperref}
\usepackage{xcolor}
\usepackage{parskip}

\definecolor{accent}{HTML}{2A4D69}

\titleformat{\section}
  {\normalfont\Large\bfseries\color{accent}}
  {}{0em}{}
  [\vspace{-0.4em}\titlerule]
\titlespacing*{\section}{0pt}{1.1em}{0.5em}

\titleformat{\subsection}
  {\normalfont\large\bfseries\color{accent}}
  {}{0em}{}
\titlespacing*{\subsection}{0pt}{0.9em}{0.3em}

\setlist[itemize]{leftmargin=1.2em, itemsep=2pt, topsep=2pt}

\pagestyle{empty}
\setlength{\parindent}{0pt}

% pandoc emits \tightlist inside compact list items; its own default
% templates define this macro, but a custom template must provide it too,
% or compilation fails with "Undefined control sequence".
\providecommand{\tightlist}{%
  \setlength{\itemsep}{0pt}\setlength{\parskip}{0pt}}

\begin{document}

$body$

\end{document}
```

This is a **pandoc template**: pandoc converts the resume Markdown into LaTeX body
content (headings become `\section`/`\subsection`, bullet lists become `itemize`, etc.)
and substitutes it in place of `$body$`. The rest of the file is just styling — a
colored section-heading rule, tight list spacing, no page numbers, and comfortable
margins, so the output reads like an actual resume rather than a raw article.

---

## Step 2 — Build `src/document_export.py`

This module mirrors the style of `src/resume_renderer.py` and `src/document_loader.py`:
plain functions, a dedicated error class, and no Streamlit imports (so it can be unit
tested and reused independently of the UI).

```python
from __future__ import annotations

import hashlib
import tempfile
from pathlib import Path

import pypandoc


class DocumentExportError(RuntimeError):
    """
    Raised when a resume document could not be exported to PDF or DOCX.
    """


_TEMPLATE_PATH = Path(__file__).resolve().parents[1] / "templates" / "resume_template.tex"


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
    """

    return _convert_markdown(
        markdown_text,
        to_format="pdf",
        extra_args=[
            "--template",
            str(_TEMPLATE_PATH),
            "--pdf-engine=tectonic",
        ],
    )


def render_resume_docx(markdown_text: str) -> bytes:
    """
    Convert the resume Markdown into a Word (.docx) document.
    """

    return _convert_markdown(markdown_text, to_format="docx")


def markdown_content_hash(markdown_text: str) -> str:
    """
    Stable hash used to cache generated documents per resume content.
    """

    return hashlib.sha256(markdown_text.encode("utf-8")).hexdigest()
```

Notes:
- `render_resume_pdf` passes `--template` (our file from Step 1) and
  `--pdf-engine=tectonic` so pandoc drives the whole Markdown → LaTeX → PDF pipeline.
- `render_resume_docx` needs no template — pandoc's built-in Markdown → DOCX conversion
  already produces a normal, editable Word document.
- `markdown_content_hash` will be used in Step 3 to avoid re-running the (relatively
  slow) LaTeX compilation on every Streamlit rerun when the resume content hasn't
  changed.

---

## Step 3 — Wire the tab into `app.py`

### 3a. Update imports

At the top of `app.py`, add:

```python
import base64
```

and extend the `src.resume_renderer` import block with a new import:

```python
from src.document_export import (
    DocumentExportError,
    markdown_content_hash,
    render_resume_docx,
    render_resume_pdf,
)
```

### 3b. Replace `_render_updated_resume`

Find `_render_updated_resume` in `app.py` (around line 284) and replace it entirely with:

```python
def _render_updated_resume_tab(final_result) -> None:
    """
    Display the updated resume, a LaTeX-typeset preview, and document downloads.
    """

    st.subheader("Updated Resume")

    updated_resume = render_updated_resume(
        final_result.final_resume_markdown or final_result.resume_revision
    )

    st.markdown(updated_resume)

    st.download_button(
        label="Download updated resume as Markdown",
        data=updated_resume,
        file_name="updated_resume.md",
        mime="text/markdown",
    )

    st.markdown("---")
    st.subheader("Typeset Preview")

    cache_key = f"resume_documents_{markdown_content_hash(updated_resume)}"

    if st.button("Generate preview", key="generate_resume_documents"):
        with st.spinner("Typesetting resume with LaTeX..."):
            try:
                st.session_state[cache_key] = {
                    "pdf": render_resume_pdf(updated_resume),
                    "docx": render_resume_docx(updated_resume),
                }
            except DocumentExportError as exc:
                st.error(str(exc))

    documents = st.session_state.get(cache_key)

    if documents:
        pdf_base64 = base64.b64encode(documents["pdf"]).decode("utf-8")
        st.markdown(
            f'<iframe src="data:application/pdf;base64,{pdf_base64}" '
            'width="100%" height="800" style="border: 1px solid #ccc;"></iframe>',
            unsafe_allow_html=True,
        )

        col1, col2 = st.columns(2)

        with col1:
            st.download_button(
                label="Download as Word (.docx)",
                data=documents["docx"],
                file_name="updated_resume.docx",
                mime=(
                    "application/vnd.openxmlformats-officedocument"
                    ".wordprocessingml.document"
                ),
            )

        with col2:
            st.download_button(
                label="Download as PDF",
                data=documents["pdf"],
                file_name="updated_resume.pdf",
                mime="application/pdf",
            )
    else:
        st.info(
            "Click **Generate preview** to typeset this resume with LaTeX "
            "before downloading."
        )
```

Why cache in `st.session_state` keyed by a content hash: Streamlit reruns the entire
script on every interaction (e.g. clicking a download button). Without caching, opening
the tab or clicking a download button would silently re-run the LaTeX compilation every
time. Keying by a hash of `updated_resume` means the cached documents stay valid until
the actual resume content changes, and a fresh run naturally gets a fresh cache key.

### 3c. Add the 4th tab

Find the tab block in `main()` (around line 450) and change it from 3 tabs to 4:

```python
tab1, tab2, tab3, tab4 = st.tabs(
    [
        "Job Match Review",
        "Suggested Resume Changes",
        "Review Steps",
        "Updated Resume",
    ]
)

with tab1:
    _render_agent_1_output(final_result)

with tab2:
    _render_agent_2_output(final_result)

with tab3:
    _render_workflow_trace(final_result)

with tab4:
    _render_updated_resume_tab(final_result)
```

---

## Step 4 — Tests

Create `tests/test_document_export.py`, following the style of
`tests/test_resume_renderer.py` and `tests/test_document_loader.py`. The mocked tests
check pandoc is invoked correctly without requiring the LaTeX toolchain; the end-to-end
tests actually compile a resume (safe here since `pandoc`/`tectonic` are installed).

```python
from __future__ import annotations

import shutil
from unittest.mock import patch

import pytest

from src.document_export import (
    DocumentExportError,
    render_resume_docx,
    render_resume_pdf,
)


def test_render_resume_pdf_calls_pandoc_with_template_and_tectonic() -> None:
    def fake_convert(text, to, format, outputfile, extra_args):
        with open(outputfile, "wb") as handle:
            handle.write(b"%PDF-fake")

    with patch(
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

    with patch(
        "src.document_export.pypandoc.convert_text", side_effect=fake_convert
    ) as mock_convert:
        docx_bytes = render_resume_docx("# Resume")

    assert docx_bytes.startswith(b"PK\x03\x04")

    _, kwargs = mock_convert.call_args
    assert kwargs["to"] == "docx"


def test_render_resume_pdf_wraps_pandoc_failure() -> None:
    with patch(
        "src.document_export.pypandoc.convert_text",
        side_effect=RuntimeError("pandoc exploded"),
    ):
        with pytest.raises(DocumentExportError, match="pandoc exploded"):
            render_resume_pdf("# Resume")


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
```

---

## Verification Checklist

- [ ] `streamlit run app.py` starts without import errors.
- [ ] Click **Load sample data** in the sidebar, then **Generate tailored suggestions**.
- [ ] Open the new **Updated Resume** tab — the Markdown preview renders as before.
- [ ] Click **Generate preview** — after a short spinner, an inline PDF preview appears
      showing a typeset resume (colored section headers, bullet lists, no visible LaTeX
      markup — not raw `\section{...}` text).
- [ ] **Download as Word (.docx)** produces a file that opens correctly in Word/Google
      Docs/Pages.
- [ ] **Download as PDF** produces a file that opens correctly and matches the preview.
- [ ] Clicking a download button does *not* re-trigger LaTeX compilation (no spinner) —
      confirms the session-state cache is working.
- [ ] `pytest` passes, including the 5 tests in `tests/test_document_export.py`.

---

## Stretch Goals (optional)

- Let the user pick between two or three different `templates/*.tex` resume styles via a
  `st.selectbox`, and pass the chosen template path into `render_resume_pdf`.
- Add a **Regenerate** button that clears the cached entry for the current content hash
  and re-runs the LaTeX compilation, useful if you tweak the template and want to see the
  effect on an already-generated resume without changing the resume text.
- Pass resume metadata (e.g. a name/title extracted from the Markdown) into pandoc as
  template variables (`--metadata title="..."`) and use `$title$` in the LaTeX template
  for a running header or PDF document title.
