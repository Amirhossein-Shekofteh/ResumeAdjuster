# Workshop Task V2: "Updated Resume" Tab with LaTeX Preview + Word/PDF Download

## Goal

ResumeAdjuster already runs two agents (a gap analyst and a resume revision agent) and
produces a fully revised resume as **Markdown text**. Right now that text is only shown
on screen — there's no way to get a real, submittable document out of it.

In this task you'll add a **4th tab, "Updated Resume"**, that:

1. Shows a Before/After Markdown comparison of the original and updated resume.
2. Lets the user click **Generate preview** to typeset the updated resume using
   **LaTeX**, producing a properly formatted document instead of plain text.
3. Shows an inline **PDF preview** of the typeset resume.
4. Offers two download buttons: **Word (.docx)** and **PDF**.

This is a trimmed-down version of the original `WORKSHOP_TASK.md`. The hard part — the
pandoc/LaTeX plumbing and the Markdown-normalization it depends on — is already built
and tested for you. You have **two steps**: wire the UI, and make the PDF your own.

---

> **Before you start:** complete [WORKSHOP_PREREQUISITES.md](WORKSHOP_PREREQUISITES.md)
> first (Python, venv, `pip install -r requirements.txt`, and installing `pandoc` +
> `tectonic`). Everything below assumes that's already done.

---

## Already built for you

- **`src/resume_markdown.py`** — `normalize_resume_markdown()` turns plain-text resumes
  (or agent output that isn't consistently Markdown) into real Markdown with `#`/`##`
  headings and consistent `- ` bullets, and `extract_resume_title()` splits the
  resume owner's name off as a document title.
- **`src/document_export.py`** — `render_resume_pdf()` and `render_resume_docx()`
  convert normalized resume Markdown into real documents via `pandoc` (+ `tectonic` for
  PDF), plus `markdown_content_hash()` for caching.
- **`templates/resume_template.tex`** — a working LaTeX resume template (colored
  section headers with a rule underneath, tight list spacing, sensible margins).
- **`tests/test_resume_markdown.py`** and **`tests/test_document_export.py`** — full
  coverage for both of the above, including real (not mocked) pandoc/tectonic
  end-to-end tests.

### Why this needed more than "just call pandoc"

Two real bugs showed up when this was first tried against an actual resume, and both
are already fixed in the code above:

1. **Section headers got the wrong styling.** A resume's Markdown naturally comes out
   as `# Name` (the person) followed by `## EDUCATION`, `## SKILLS`, etc. (the actual
   sections). Pandoc maps level-1 headings to LaTeX `\section` and level-2 to
   `\subsection` — so the *name* got the template's prominent colored-rule styling, and
   every real *section* got a plainer, unruled style. Backwards from how a resume
   should look. The fix: `document_export.py`'s `render_resume_pdf()` pulls the name
   out with `extract_resume_title()` and passes it to pandoc as `--metadata title=...`
   instead of leaving it as a heading, then shifts the remaining heading levels with
   `--shift-heading-level-by=-1` so every real section maps to `\section` uniformly.
   The name renders as a plain centered title in the template instead.
2. **Bullets glued to the line above them silently became run-on text.** Markdown
   requires a blank line between a paragraph and a following bullet list; a resume
   line like a job title/date immediately followed by `- ...` bullets with no blank
   line in between gets treated as a lazy continuation of that paragraph by pandoc (and
   by Streamlit's on-screen Markdown renderer) — the bullets never render as a list at
   all, just run-on text joined by `" - "`. `normalize_resume_markdown()` now inserts
   the missing blank line automatically.

Both were confirmed by actually compiling a real resume through the pipeline and
inspecting the output PDF, not just by reading the code — worth doing the same
yourself once you've finished Step 1 (see the Verification Checklist).

---

## Step 1 — Wire the tab into `app.py`

### 1a. Update imports

Add this new import block near the other `src` imports (after the existing
`from src.resume_renderer import (...)` block, around line 17):

```python
from src.document_export import (
    DocumentExportError,
    markdown_content_hash,
    render_resume_docx,
    render_resume_pdf,
)
from src.resume_markdown import normalize_resume_markdown
```

At the top of `app.py`, also add:

```python
import base64
```

### 1b. Replace `_render_updated_resume`

Find `_render_updated_resume` in `app.py` (around line 340) and replace it entirely
with:

```python
def _render_updated_resume_tab(final_result, original_resume: str) -> None:
    """
    Display a before/after resume comparison, a LaTeX-typeset preview, and downloads.
    """

    st.subheader("Updated Resume")

    updated_resume = render_updated_resume(
        final_result.final_resume_markdown or final_result.resume_revision
    )

    st.markdown("---")
    st.subheader("Before / After")

    col_before, col_after = st.columns(2)

    with col_before:
        st.markdown("**Original Resume**")
        st.markdown(
            normalize_resume_markdown(original_resume)
            if original_resume
            else "_No original resume text available._"
        )

    with col_after:
        st.markdown("**Updated Resume**")
        st.markdown(normalize_resume_markdown(updated_resume))

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

Two things worth understanding, not just copying:

- **Why `normalize_resume_markdown` is called here, and only here (for the on-screen
  preview) or inside `document_export.py` (for the PDF/DOCX):** `updated_resume` and
  `original_resume` are the raw values used elsewhere too (the Markdown download
  button, the cache key). `normalize_resume_markdown` is applied only at the point
  each value is actually rendered or exported — never assigned back into those
  variables, and never fed to Agent 1, Agent 2, or the deterministic checkers in
  `src/checks/resume_revision_checker.py`. That checker requires `evidence_source` to
  be an exact substring of the raw resume text; normalizing that text upstream of the
  agents would silently break grounding checks.
- **Why cache in `st.session_state` keyed by a content hash:** Streamlit reruns the
  entire script on every interaction (e.g. clicking a download button). Without
  caching, opening the tab or clicking a download button would silently re-run the
  LaTeX compilation every time. Keying by a hash of `updated_resume` means the cached
  documents stay valid until the actual resume content changes.

### 1c. Add the 4th tab, first

Find the tab block in `main()` (around line 663) and change it from 3 tabs to 4. Put
**"Updated Resume" first**: for a non-technical user, the final revised resume is the
actual deliverable, so it should be the tab they land on rather than something they
have to dig for.

```python
tab1, tab2, tab3, tab4 = st.tabs(
    [
        "Updated Resume",
        "Suggested Resume Changes",
        "Job Match Review",
        "Review Steps",
    ]
)

with tab1:
    _render_updated_resume_tab(
        final_result, st.session_state.get("source_resume_text", "")
    )

with tab2:
    _render_agent_2_output(final_result)

with tab3:
    _render_agent_1_output(final_result)

with tab4:
    _render_workflow_trace(final_result)
```

`source_resume_text` is already set alongside `final_result` in `main()`'s
`st.session_state["source_resume_text"] = current_resume` line (around line 648) —
it's the resume text that was actually used to produce this `final_result`, so the
"Before" side of the Before/After view stays correct even if the user edits the resume
text area afterward without regenerating.

---

## Step 2 — Personalize `templates/resume_template.tex`

The template you have compiles correctly and looks good — that's your working
baseline, not a starting point to build from scratch. Your job is to make it your own,
then prove it still works.

Ideas (pick at least one, or do all of them):

- Change `\definecolor{accent}{HTML}{2A4D69}` to a different accent color.
- Adjust `\usepackage[margin=0.75in]{geometry}`'s margin, or the spacing values in
  `\titlespacing*{\section}{0pt}{1.1em}{0.5em}`.
- Try a different font package (e.g. `\usepackage{lmodern}` or a serif/sans-serif
  package of your choice) instead of the LaTeX default.
- Change the `\titleformat{\section}` rule style — e.g. a thicker `\titlerule`, or a
  different placement.

**Whatever you change, re-verify against the Verification Checklist below before
considering this done.** It's easy to break the rule/spacing this whole feature
depends on with a small `\titleformat` edit — for example, forgetting to keep the
`[\vspace{-0.4em}\titlerule]` argument removes the heading rule entirely, or removing
the empty `{}` label argument makes LaTeX print visible section numbers.

---

## Verification Checklist

- [ ] `streamlit run app.py` starts without import errors.
- [ ] Click **Load sample data** in the sidebar — all three fields populate with sample
      content.
- [ ] Click **Generate tailored suggestions** — **Updated Resume** is the first,
      default-active tab (not the last one).
- [ ] The **Updated Resume** tab shows a "Before / After" section with the original
      resume and the updated resume side by side, both rendering with visible headings
      (not raw `#`/`##` characters or unformatted plain text).
- [ ] Click **Generate preview** — after a short spinner, an inline PDF preview appears
      showing a typeset resume — and the other tabs/results remain visible after this
      rerun.
- [ ] In the generated PDF: the resume owner's name renders as a plain centered title
      (no colored rule under it), and **every section** (Education, Skills, Experience,
      ...) — not just the first one — renders with the template's colored heading and
      rule underneath.
- [ ] Bullet points under each job/project entry render as an actual bulleted list in
      the PDF, not as run-on text joined by dashes.
- [ ] **Download as Word (.docx)** produces a file that opens correctly in Word/Google
      Docs/Pages.
- [ ] **Download as PDF** produces a file that opens correctly and matches the preview.
- [ ] Clicking a download button does *not* re-trigger LaTeX compilation (no spinner) —
      confirms the session-state cache is working.
- [ ] After your Step 2 template edit, all of the above still hold — re-run through the
      checklist once more with your personalized template.
- [ ] `pytest` passes (`src/resume_markdown.py` and `src/document_export.py` already
      have full test coverage — Step 1/2 don't require new tests, but should not break
      the existing ones).

---

## Stretch Goals (optional)

- Let the user pick between two or three different `templates/*.tex` resume styles via
  a `st.selectbox`, and pass the chosen template path into `render_resume_pdf`.
- Add a **Regenerate** button that clears the cached entry for the current content hash
  and re-runs the LaTeX compilation, useful if you tweak the template and want to see
  the effect on an already-generated resume without changing the resume text.
- Pass additional resume metadata (e.g. a target job title) into pandoc as template
  variables and use it in the LaTeX template for a running header.
