from __future__ import annotations

import html
from pathlib import Path

import streamlit as st

from src.config import CONFIG
from src.document_loader import DocumentLoadingError, load_document
from src.graph.runner import stream_resume_adjuster
from src.llm_client import LLMClient
from src.resume_renderer import (
    render_change_summary,
    render_final_report,
    render_gap_analysis_summary,
    render_updated_resume,
)
from src.schemas import AgentTraceStep, FinalWorkflowResult


APP_TITLE = "ResumeAdjuster"
APP_SUBTITLE = "Tailor suggestions for the resume to a target job using truthful evidence from coursework and experience"


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


PROVIDER_LABELS = {"gemini": "Gemini", "openai": "OpenAI"}


def _default_provider() -> str:
    """
    Pick a sensible default provider based on which API key is available.
    """

    has_gemini_key = bool(CONFIG.gemini_api_key)
    has_openai_key = bool(CONFIG.openai_api_key)

    if has_gemini_key and not has_openai_key:
        return "gemini"

    if has_openai_key and not has_gemini_key:
        return "openai"

    return CONFIG.llm_provider


def _render_provider_picker() -> str:
    """
    Render the LLM provider selector and return the chosen provider key.
    """

    options = ["gemini", "openai"]
    default_provider = _default_provider()
    default_index = options.index(default_provider) if default_provider in options else 0

    selected_label = st.sidebar.selectbox(
        "LLM Provider",
        options=[PROVIDER_LABELS[option] for option in options],
        index=default_index,
        help="Choose which LLM provider to use for generating suggestions.",
    )

    return next(key for key, label in PROVIDER_LABELS.items() if label == selected_label)


def _provider_model_name(provider: str) -> str:
    return CONFIG.gemini_model if provider == "gemini" else CONFIG.openai_model


def _provider_api_key(provider: str) -> str | None:
    return CONFIG.gemini_api_key if provider == "gemini" else CONFIG.openai_api_key


def _provider_env_var_name(provider: str) -> str:
    return "GEMINI_API_KEY" if provider == "gemini" else "OPENAI_API_KEY"


def _render_api_key_notice(provider: str) -> None:
    """
    Show API-key status without exposing secret values.
    """

    label = PROVIDER_LABELS[provider]

    if _provider_api_key(provider):
        st.sidebar.success(f"{label} API key detected.")
    else:
        st.sidebar.warning(
            f"{label} API key is not set yet. You can build and view the app, "
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


def _render_review_gate(review_gate) -> None:
    """
    Display a reviewer-gate verdict (scope/boundary check), if present.
    """

    if review_gate is None:
        return

    with st.expander("Scope & Safety Review", expanded=review_gate.verdict != "approved"):
        if review_gate.verdict == "approved":
            st.success("Approved: no scope or safety concerns detected.")
        elif review_gate.verdict == "needs_human_review":
            st.warning("Needs human review.")
        else:
            st.error("Blocked: scope or safety violation detected.")

        if review_gate.blockers:
            st.markdown("**Blockers:**")
            for blocker in review_gate.blockers:
                st.markdown(f"- {blocker}")

        if review_gate.warnings:
            st.markdown("**Warnings:**")
            for warning in review_gate.warnings:
                st.markdown(f"- {warning}")

        if review_gate.human_review_reason:
            st.caption(review_gate.human_review_reason)

        if review_gate.policy_notes:
            st.markdown("**Scope policy:**")
            for note in review_gate.policy_notes:
                st.markdown(f"- {note}")


def _render_agent_1_output(final_result) -> None:
    """
    Display Agent 1 output.
    """

    st.subheader("Job Match Review")

    if final_result.gap_analysis is None:
        st.info("No gap analysis was generated.")
        return

    gap_analysis = final_result.gap_analysis

    col1, col2, col3 = st.columns(3)
    col1.metric("Estimated Fit", f"{gap_analysis.estimated_fit_score}/100")
    col2.metric("Requirements", len(gap_analysis.job_requirements))
    col3.metric("Gaps", len(gap_analysis.gaps))

    _render_review_gate(final_result.agent1_review_gate)

    st.markdown(render_gap_analysis_summary(gap_analysis))


def _render_agent_2_output(final_result) -> None:
    """
    Display Agent 2 output.
    """

    st.subheader("Suggested Resume Changes")

    if final_result.resume_revision is None:
        st.info("No resume revision was generated.")
        return

    resume_revision = final_result.resume_revision

    if resume_revision.decision == "keep_already_strong":
        st.success("Agent 2 decided to keep your resume unchanged: it's already strong for this role.")
    elif resume_revision.decision == "keep_insufficient_fit":
        st.warning(
            "Agent 2 decided to keep your resume unchanged: there wasn't enough "
            "truthful evidence to strengthen it for this role."
        )

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Changes", len(resume_revision.changes))
    col2.metric("Keywords Added", len(resume_revision.added_keywords))
    col3.metric("Warnings", len(resume_revision.warnings))
    col4.metric("Confidence", f"{resume_revision.semantic_confidence}/100")

    if resume_revision.semantic_warnings:
        with st.expander(
            "Truthfulness & Consistency Warnings",
            expanded=resume_revision.semantic_confidence < 100,
        ):
            for warning in resume_revision.semantic_warnings:
                st.markdown(f"- {warning}")

    _render_review_gate(final_result.agent2_review_gate)

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


_STEP_STATUS_STYLE = {
    "success": {"icon": "&#9989;", "color": "#22c55e", "label": "Success"},
    "warning": {"icon": "&#9888;&#65039;", "color": "#f59e0b", "label": "Warning"},
    "error": {"icon": "&#10060;", "color": "#ef4444", "label": "Error"},
}


def _build_stepper_html(agent_trace: list[AgentTraceStep]) -> str | None:
    """
    Build the HTML for a vertical, node-level progress stepper from an
    agent_trace. Returns None if there are no steps yet.
    """

    if not agent_trace:
        return None

    steps_html: list[str] = []

    for index, step in enumerate(agent_trace):
        style = _STEP_STATUS_STYLE.get(
            step.status, {"icon": "&#8226;", "color": "#94a3b8", "label": step.status}
        )
        is_last = index == len(agent_trace) - 1
        agent_label = html.escape(step.agent_name or "Workflow node")
        step_title = html.escape(f"Step {step.step_number}: {step.step_name}")
        input_summary = html.escape(step.input_summary)
        output_summary = html.escape(step.output_summary)

        steps_html.append(
            f"""
            <div class="ra-step{'' if not is_last else ' ra-step-last'}">
                <div class="ra-step-marker">
                    <span class="ra-step-icon" style="background:{style['color']}">{style['icon']}</span>
                    {'' if is_last else '<span class="ra-step-line"></span>'}
                </div>
                <div class="ra-step-body">
                    <div class="ra-step-header">
                        <span class="ra-step-title">{step_title}</span>
                        <span class="ra-step-agent">{agent_label}</span>
                        <span class="ra-step-status" style="color:{style['color']}">{style['label']}</span>
                    </div>
                    <div class="ra-step-summary"><strong>In:</strong> {input_summary}</div>
                    <div class="ra-step-summary"><strong>Out:</strong> {output_summary}</div>
                </div>
            </div>
            """
        )

    stepper_html = f"""
    <style>
    .ra-stepper {{
        display: flex;
        flex-direction: column;
    }}
    .ra-step {{
        display: flex;
        gap: 0.75rem;
    }}
    .ra-step-marker {{
        display: flex;
        flex-direction: column;
        align-items: center;
        flex-shrink: 0;
    }}
    .ra-step-icon {{
        display: flex;
        align-items: center;
        justify-content: center;
        width: 1.75rem;
        height: 1.75rem;
        border-radius: 50%;
        font-size: 0.9rem;
        color: white;
    }}
    .ra-step-line {{
        flex: 1;
        width: 2px;
        min-height: 1.5rem;
        background: rgba(128, 128, 128, 0.35);
        margin: 0.15rem 0;
    }}
    .ra-step-body {{
        flex: 1;
        padding-bottom: 1.25rem;
    }}
    .ra-step-last .ra-step-body {{
        padding-bottom: 0;
    }}
    .ra-step-header {{
        display: flex;
        flex-wrap: wrap;
        align-items: baseline;
        gap: 0.5rem;
        margin-bottom: 0.25rem;
    }}
    .ra-step-title {{
        font-weight: 600;
        color: var(--text-color);
    }}
    .ra-step-agent {{
        font-size: 0.75rem;
        padding: 0.05rem 0.5rem;
        border-radius: 999px;
        background: rgba(128, 128, 128, 0.2);
        color: var(--text-color);
    }}
    .ra-step-status {{
        font-size: 0.75rem;
        font-weight: 600;
        text-transform: uppercase;
    }}
    .ra-step-summary {{
        font-size: 0.85rem;
        color: var(--text-color);
        opacity: 0.75;
        margin: 0.1rem 0;
    }}
    </style>
    <div class="ra-stepper">
        {''.join(steps_html)}
    </div>
    """

    # st.markdown parses via CommonMark, which treats 4-space-indented lines as
    # a code block. The f-string above is built inside indented Python, so it
    # would otherwise render as literal escaped text instead of HTML.
    return "\n".join(line.strip() for line in stepper_html.strip().splitlines())


def _render_workflow_trace(final_result) -> None:
    """
    Display a node-level progress tracker for the agentic workflow as a vertical stepper.
    """

    st.subheader("Review Steps")

    stepper_html = _build_stepper_html(final_result.agent_trace)

    if stepper_html is None:
        st.info("No workflow trace available.")
        return

    st.markdown(stepper_html, unsafe_allow_html=True)


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

    st.sidebar.header("ResumeAdjuster")
    st.sidebar.markdown(
        """
    This tool helps tailor a resume to a target job using only truthful information from:

    - the current resume
    - the job description
    - coursework and student background details
    """
                        )
    provider = _render_provider_picker()

    with st.sidebar.expander("Developer details"):
        st.write(f"Provider: `{PROVIDER_LABELS[provider]}`")
        st.write(f"Model: `{_provider_model_name(provider)}`")
        st.write(f"Temperature: `{CONFIG.model_temperature}`")
        st.write(f"Max input length: `{CONFIG.max_input_text_length}` characters")
        _render_api_key_notice(provider)

    if st.sidebar.button("Load sample data"):
        _load_samples_into_session()
        st.rerun()

    st.sidebar.markdown("---")
    st.sidebar.markdown(
    """
    **How it works**

    1. Review the resume and job description  
    2. Identify important job requirements and resume gaps  
    3. Use coursework/background information to improve the resume honestly  
    4. Generate suggestions and change summary
    """
    )

    job_description, current_resume, coursework_student_info = _render_input_section()

    input_errors = _validate_inputs(
        job_description=job_description,
        current_resume=current_resume,
        coursework_student_info=coursework_student_info,
    )

    run_clicked = st.button("Generate tailored suggestions", type="primary")

    if run_clicked:
        if input_errors:
            for error in input_errors:
                st.error(error)
            return

        if not _provider_api_key(provider):
            env_var_name = _provider_env_var_name(provider)
            st.error(
                f"{env_var_name} is not set. Add your API key to the local `.env` file "
                "before running the agents."
            )
            st.code(
                f"LLM_PROVIDER={provider}\n"
                f"{env_var_name}=your_real_key_here\n"
                f"{'GEMINI_MODEL' if provider == 'gemini' else 'OPENAI_MODEL'}="
                f"{_provider_model_name(provider)}\n"
                "MODEL_TEMPERATURE=0.2\n"
                "MAX_INPUT_TEXT_LENGTH=20000",
                language="text",
            )
            return

        llm_client = LLMClient(provider=provider)
        final_result = None

        with st.status(
            "Reviewing the resume and generating suggestions...", expanded=True
        ) as status:
            stepper_placeholder = st.empty()

            for item in stream_resume_adjuster(
                job_description=job_description,
                current_resume=current_resume,
                coursework_student_info=coursework_student_info,
                llm_client=llm_client,
            ):
                if isinstance(item, FinalWorkflowResult):
                    final_result = item
                else:
                    stepper_html = _build_stepper_html(item)
                    if stepper_html is not None:
                        stepper_placeholder.markdown(stepper_html, unsafe_allow_html=True)

            if final_result is not None and final_result.success:
                status.update(
                    label="Tailored suggestions generated.",
                    state="complete",
                    expanded=False,
                )
            else:
                status.update(
                    label="Resume review completed with issues.",
                    state="error",
                    expanded=False,
                )

        st.session_state["final_result"] = final_result
        st.session_state["source_resume_text"] = current_resume

    final_result = st.session_state.get("final_result")

    if final_result is not None:
        if final_result.success:
            st.success("Tailored suggestions generated.")
        else:
            st.warning("Resume review completed, but some issues need attention.")

        if final_result.errors:
            with st.expander("Errors", expanded=True):
                for error in final_result.errors:
                    st.error(error)

        tab1, tab2, tab3 = st.tabs(
            [
                "Suggested Resume Changes",
                "Job Match Review",
                "Review Steps",
            ]
        )

        with tab1:
            _render_agent_2_output(final_result)

        with tab2:
            _render_agent_1_output(final_result)

        with tab3:
            _render_workflow_trace(final_result)

    else:
        st.info(
            "Upload or paste your resume, target job description, and "
            "coursework/background information, then click "
            "**Generate tailored suggestions**."
        )


if __name__ == "__main__":
    main()