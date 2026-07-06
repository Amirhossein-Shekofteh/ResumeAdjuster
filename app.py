from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from src.config import CONFIG
from src.document_loader import DocumentLoadingError, load_document
from src.graph.runner import run_resume_adjuster
from src.resume_renderer import (
    render_change_summary,
    render_final_report,
    render_gap_analysis_summary,
    render_updated_resume,
)
from src.utils.logging_utils import trace_to_rows


APP_TITLE = "ResumeAdjuster"
APP_SUBTITLE = "Two-agent LangGraph demo for tailoring a student resume to a target job"


def _allowed_upload_types() -> list[str]:
    """
    Convert allowed file types from('.txt', '.pdf', '.docx') to Streamlit format.
    """

    return [extension.replace(".", "") for extension in CONFIG.allowed_file_types]


def _load_uploaded_file(uploaded_file, field_label: str) -> str:
    """
    Load text from a Streamlit uploaded file.
    """

    if uploaded_file is None:
        return ""

    try:
        return load_document(uploaded_file, filename=uploaded_file.name)
    except DocumentLoadingError as exc:
        raise ValueError(f"Could not load {field_label}: {exc}") from exc


def _get_input_text(
    uploaded_file,
    pasted_text: str,
    field_label: str,
) -> str:
    """
    Prefer uploaded file content if provided; otherwise use pasted text.
    """

    if uploaded_file is not None:
        return _load_uploaded_file(uploaded_file, field_label=field_label)

    return pasted_text.strip()


def _read_sample_file(path: str) -> str:
    """
    Read a sample file if it exists.
    """

    sample_path = Path(path)

    if not sample_path.exists():
        return ""

    return sample_path.read_text(encoding="utf-8")


def _render_api_key_notice() -> None:
    """
    Show API-key status without exposing secret values.
    """

    if CONFIG.openai_api_key:
        st.sidebar.success("OpenAI API key detected.")
    else:
        st.sidebar.warning(
            "OpenAI API key is not set yet. You can build and view the app, "
            "but the agent workflow will need a key before it can run."
        )


def _render_input_section() -> tuple[str, str, str]:
    """
    Render all user inputs and return raw text values.
    """

    st.header("Inputs")

    allowed_types = _allowed_upload_types()

    with st.expander("1. Current resume", expanded=True):
        resume_file = st.file_uploader(
            "Upload resume",
            type=allowed_types,
            key="resume_file",
            help="Supported formats: TXT, PDF, DOCX.",
        )
        resume_text = st.text_area(
            "Or paste resume text",
            value=st.session_state.get("sample_resume", ""),
            height=220,
            placeholder="Paste the student's current resume here...",
        )

    with st.expander("2. Target job description", expanded=True):
        job_file = st.file_uploader(
            "Upload job description",
            type=allowed_types,
            key="job_file",
            help="Supported formats: TXT, PDF, DOCX.",
        )
        job_text = st.text_area(
            "Or paste job description",
            value=st.session_state.get("sample_job_description", ""),
            height=220,
            placeholder="Paste the target job description here...",
        )

    with st.expander("3. Coursework and student background information", expanded=True):
        coursework_file = st.file_uploader(
            "Upload coursework / student background information",
            type=allowed_types,
            key="coursework_file",
            help="Supported formats: TXT, PDF, DOCX.",
        )
        coursework_text = st.text_area(
            "Or paste coursework and student background information",
            value=st.session_state.get("sample_coursework", ""),
            height=220,
            placeholder=(
                "Paste relevant courses, class projects, labs, tools, "
                "certifications, assignments, and student background details..."
            ),
        )

    try:
        current_resume = _get_input_text(
            uploaded_file=resume_file,
            pasted_text=resume_text,
            field_label="resume",
        )
        job_description = _get_input_text(
            uploaded_file=job_file,
            pasted_text=job_text,
            field_label="job description",
        )
        coursework_student_info = _get_input_text(
            uploaded_file=coursework_file,
            pasted_text=coursework_text,
            field_label="coursework/student information",
        )
    except ValueError as exc:
        st.error(str(exc))
        return "", "", ""

    return job_description, current_resume, coursework_student_info


def _validate_inputs(
    job_description: str,
    current_resume: str,
    coursework_student_info: str,
) -> list[str]:
    """
    Validate required app inputs.
    """

    errors: list[str] = []

    if not current_resume.strip():
        errors.append("Resume is required.")

    if not job_description.strip():
        errors.append("Job description is required.")

    if not coursework_student_info.strip():
        errors.append("Coursework/student background information is required.")

    return errors


def _render_agent_1_output(final_result) -> None:
    """
    Display Agent 1 output.
    """

    st.subheader("Agent 1 Output: Job-Resume Gap Analysis")

    if final_result.gap_analysis is None:
        st.info("No gap analysis was generated.")
        return

    gap_analysis = final_result.gap_analysis

    col1, col2, col3 = st.columns(3)
    col1.metric("Estimated Fit", f"{gap_analysis.estimated_fit_score}/100")
    col2.metric("Requirements", len(gap_analysis.job_requirements))
    col3.metric("Gaps", len(gap_analysis.gaps))

    st.markdown(render_gap_analysis_summary(gap_analysis))


def _render_agent_2_output(final_result) -> None:
    """
    Display Agent 2 output.
    """

    st.subheader("Agent 2 Output: Resume Revision")

    if final_result.resume_revision is None:
        st.info("No resume revision was generated.")
        return

    resume_revision = final_result.resume_revision

    col1, col2, col3 = st.columns(3)
    col1.metric("Changes", len(resume_revision.changes))
    col2.metric("Keywords Added", len(resume_revision.added_keywords))
    col3.metric("Warnings", len(resume_revision.warnings))

    st.markdown(render_change_summary(resume_revision))


def _render_updated_resume(final_result) -> None:
    """
    Display and download the updated resume.
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


def _render_workflow_trace(final_result) -> None:
    """
    Display workflow trace for the agentic AI demo.
    """

    st.subheader("Workflow Trace")

    if not final_result.agent_trace:
        st.info("No workflow trace available.")
        return

    trace_rows = trace_to_rows(final_result.agent_trace)
    trace_df = pd.DataFrame(trace_rows)

    st.dataframe(trace_df, use_container_width=True, hide_index=True)


def _render_full_report_download(final_result) -> None:
    """
    Provide a full Markdown report download.
    """

    report_markdown = render_final_report(final_result)

    st.download_button(
        label="Download full report as Markdown",
        data=report_markdown,
        file_name="resume_adjuster_report.md",
        mime="text/markdown",
    )


def _load_samples_into_session() -> None:
    """
    Load sample files into Streamlit session state.
    """

    st.session_state["sample_resume"] = _read_sample_file("data/sample_resume.txt")
    st.session_state["sample_job_description"] = _read_sample_file(
        "data/sample_job_description.txt"
    )
    st.session_state["sample_coursework"] = _read_sample_file(
        "data/sample_coursework_and_student_info.txt"
    )


def main() -> None:
    st.set_page_config(
        page_title=APP_TITLE,
        page_icon="🧭",
        layout="wide",
    )

    st.title(APP_TITLE)
    st.caption(APP_SUBTITLE)

    st.sidebar.header("Project Settings")
    st.sidebar.write(f"Model: `{CONFIG.openai_model}`")
    st.sidebar.write(f"Temperature: `{CONFIG.model_temperature}`")
    st.sidebar.write(f"Max input length: `{CONFIG.max_input_text_length}` characters")
    _render_api_key_notice()

    if st.sidebar.button("Load sample data"):
        _load_samples_into_session()
        st.rerun()

    st.sidebar.markdown("---")
    st.sidebar.markdown(
        """
        **Workflow**

        1. Clean inputs  
        2. Agent 1 analyzes job-resume gaps  
        3. Agent 2 revises the resume  
        4. Final report is generated
        """
    )

    job_description, current_resume, coursework_student_info = _render_input_section()

    input_errors = _validate_inputs(
        job_description=job_description,
        current_resume=current_resume,
        coursework_student_info=coursework_student_info,
    )

    run_clicked = st.button("Run two-agent resume adjustment", type="primary")

    if run_clicked:
        if input_errors:
            for error in input_errors:
                st.error(error)
            return

        if not CONFIG.openai_api_key:
            st.error(
                "OPENAI_API_KEY is not set. Add your API key to the local `.env` file "
                "before running the agents."
            )
            st.code(
                "OPENAI_API_KEY=your_real_key_here\n"
                "OPENAI_MODEL=gpt-4.1-mini\n"
                "MODEL_TEMPERATURE=0.2\n"
                "MAX_INPUT_TEXT_LENGTH=20000",
                language="text",
            )
            return

        with st.spinner("Running LangGraph workflow..."):
            final_result = run_resume_adjuster(
                job_description=job_description,
                current_resume=current_resume,
                coursework_student_info=coursework_student_info,
            )

        if final_result.success:
            st.success("Resume adjustment completed.")
        else:
            st.warning("Workflow completed with errors or warnings.")

        if final_result.errors:
            with st.expander("Errors", expanded=True):
                for error in final_result.errors:
                    st.error(error)

        tab1, tab2, tab3, tab4, tab5 = st.tabs(
            [
                "Agent 1: Gap Analysis",
                "Agent 2: Resume Revision",
                "Updated Resume",
                "Workflow Trace",
                "Full Report",
            ]
        )

        with tab1:
            _render_agent_1_output(final_result)

        with tab2:
            _render_agent_2_output(final_result)

        with tab3:
            _render_updated_resume(final_result)

        with tab4:
            _render_workflow_trace(final_result)

        with tab5:
            st.markdown(render_final_report(final_result))
            _render_full_report_download(final_result)

    else:
        st.info(
            "Upload or paste the three inputs, then click "
            "**Run two-agent resume adjustment**."
        )


if __name__ == "__main__":
    main()