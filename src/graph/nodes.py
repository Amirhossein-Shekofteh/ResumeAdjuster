from __future__ import annotations

from typing import Any

from src.agents.gap_analyst_agent import run_gap_analysis
from src.agents.resume_revision_agent import run_resume_revision
from src.graph.state import ResumeAdjusterState
from src.schemas import AgentTraceStep, FinalWorkflowResult
from src.text_cleaner import (
    clean_coursework_text,
    clean_job_description_text,
    clean_resume_text,
)


def _state_errors(state: ResumeAdjusterState) -> list[str]:
    """
    Return current errors from state.
    """

    return list(state.get("errors") or [])


def _has_errors(state: ResumeAdjusterState) -> bool:
    """
    Check whether previous workflow steps produced errors.
    """

    return bool(_state_errors(state))


def _required_text(state: ResumeAdjusterState, key: str) -> str:
    """
    Read a required text value from graph state.
    """

    value = state.get(key)

    if value is None:
        raise ValueError(f"Missing required state value: {key}")

    if not isinstance(value, str):
        raise TypeError(
            f"State value '{key}' must be a string. Got {type(value).__name__}."
        )

    value = value.strip()

    if not value:
        raise ValueError(f"State value '{key}' cannot be empty.")

    return value


def _trace_step(
    step_number: int,
    step_name: str,
    status: str,
    input_summary: str,
    output_summary: str,
    agent_name: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> AgentTraceStep:
    """
    Create a trace step for the UI/demo.
    """

    return AgentTraceStep(
        step_number=step_number,
        step_name=step_name,
        agent_name=agent_name,
        status=status,  # type: ignore[arg-type]
        input_summary=input_summary,
        output_summary=output_summary,
        metadata=metadata or {},
    )


def clean_inputs_node(state: ResumeAdjusterState) -> dict[str, Any]:
    """
    Node 1: Clean raw inputs.

    This is not an agent node.
    """

    try:
        job_description = _required_text(state, "job_description")
        current_resume = _required_text(state, "current_resume")
        coursework_student_info = _required_text(state, "coursework_student_info")

        cleaned_job_description = clean_job_description_text(job_description)
        cleaned_current_resume = clean_resume_text(current_resume)
        cleaned_coursework_student_info = clean_coursework_text(coursework_student_info)

        trace = _trace_step(
            step_number=1,
            step_name="Clean Inputs",
            agent_name=None,
            status="success",
            input_summary="Raw job description, resume, and coursework/student information.",
            output_summary="Cleaned and normalized all text inputs.",
            metadata={
                "cleaned_job_description_length": len(cleaned_job_description),
                "cleaned_current_resume_length": len(cleaned_current_resume),
                "cleaned_coursework_student_info_length": len(
                    cleaned_coursework_student_info
                ),
            },
        )

        return {
            "cleaned_job_description": cleaned_job_description,
            "cleaned_current_resume": cleaned_current_resume,
            "cleaned_coursework_student_info": cleaned_coursework_student_info,
            "agent_trace": [trace],
        }

    except Exception as exc:
        error_message = f"Input cleaning failed: {exc}"

        trace = _trace_step(
            step_number=1,
            step_name="Clean Inputs",
            agent_name=None,
            status="error",
            input_summary="Raw job description, resume, and coursework/student information.",
            output_summary=error_message,
        )

        return {
            "errors": [error_message],
            "agent_trace": [trace],
        }


def gap_analysis_node(state: ResumeAdjusterState) -> dict[str, Any]:
    """
    Node 2: Run Agent 1.

    Agent:
    - Job-Resume Gap Analyst

    Inputs:
    - cleaned job description
    - cleaned current resume

    Outputs:
    - GapAnalysisResult
    - RevisionBrief for Agent 2
    """

    if _has_errors(state):
        trace = _trace_step(
            step_number=2,
            step_name="Gap Analysis",
            agent_name="Job-Resume Gap Analyst",
            status="warning",
            input_summary="Skipped because previous workflow errors exist.",
            output_summary="Gap analysis was not run.",
        )

        return {"agent_trace": [trace]}

    try:
        cleaned_job_description = _required_text(state, "cleaned_job_description")
        cleaned_current_resume = _required_text(state, "cleaned_current_resume")

        gap_analysis = run_gap_analysis(
            job_description=cleaned_job_description,
            current_resume=cleaned_current_resume,
        )

        trace = _trace_step(
            step_number=2,
            step_name="Gap Analysis",
            agent_name="Job-Resume Gap Analyst",
            status="success",
            input_summary="Cleaned job description and cleaned current resume.",
            output_summary=(
                f"Generated gap analysis with {len(gap_analysis.job_requirements)} "
                f"requirements, {len(gap_analysis.gaps)} gaps, and "
                f"fit score {gap_analysis.estimated_fit_score}/100."
            ),
            metadata={
                "requirement_count": len(gap_analysis.job_requirements),
                "gap_count": len(gap_analysis.gaps),
                "low_relevance_item_count": len(gap_analysis.low_relevance_items),
                "estimated_fit_score": gap_analysis.estimated_fit_score,
            },
        )

        return {
            "gap_analysis": gap_analysis,
            "revision_brief": gap_analysis.revision_brief,
            "agent_trace": [trace],
        }

    except Exception as exc:
        error_message = f"Gap analysis failed: {exc}"

        trace = _trace_step(
            step_number=2,
            step_name="Gap Analysis",
            agent_name="Job-Resume Gap Analyst",
            status="error",
            input_summary="Cleaned job description and cleaned current resume.",
            output_summary=error_message,
        )

        return {
            "errors": [error_message],
            "agent_trace": [trace],
        }


def resume_revision_node(state: ResumeAdjusterState) -> dict[str, Any]:
    """
    Node 3: Run Agent 2.

    Agent:
    - Resume Revision Agent

    Inputs:
    - cleaned current resume
    - cleaned coursework/student information
    - revision brief from Agent 1

    Important:
    - This node does not pass the raw job description to Agent 2.
    """

    if _has_errors(state):
        trace = _trace_step(
            step_number=3,
            step_name="Resume Revision",
            agent_name="Resume Revision Agent",
            status="warning",
            input_summary="Skipped because previous workflow errors exist.",
            output_summary="Resume revision was not run.",
        )

        return {"agent_trace": [trace]}

    try:
        cleaned_current_resume = _required_text(state, "cleaned_current_resume")
        cleaned_coursework_student_info = _required_text(
            state,
            "cleaned_coursework_student_info",
        )

        revision_brief = state.get("revision_brief")

        if revision_brief is None:
            raise ValueError("Missing revision_brief from Agent 1.")

        resume_revision = run_resume_revision(
            current_resume=cleaned_current_resume,
            coursework_student_info=cleaned_coursework_student_info,
            revision_brief=revision_brief,
        )

        trace = _trace_step(
            step_number=3,
            step_name="Resume Revision",
            agent_name="Resume Revision Agent",
            status="success",
            input_summary=(
                "Cleaned current resume, cleaned coursework/student information, "
                "and Agent 1 revision brief."
            ),
            output_summary=(
                f"Generated updated resume with {len(resume_revision.changes)} "
                f"tracked changes and {len(resume_revision.warnings)} warnings."
            ),
            metadata={
                "change_count": len(resume_revision.changes),
                "added_keyword_count": len(resume_revision.added_keywords),
                "warning_count": len(resume_revision.warnings),
            },
        )

        return {
            "resume_revision": resume_revision,
            "final_resume_markdown": resume_revision.updated_resume_markdown,
            "agent_trace": [trace],
        }

    except Exception as exc:
        error_message = f"Resume revision failed: {exc}"

        trace = _trace_step(
            step_number=3,
            step_name="Resume Revision",
            agent_name="Resume Revision Agent",
            status="error",
            input_summary=(
                "Cleaned current resume, cleaned coursework/student information, "
                "and Agent 1 revision brief."
            ),
            output_summary=error_message,
        )

        return {
            "errors": [error_message],
            "agent_trace": [trace],
        }


def final_output_node(state: ResumeAdjusterState) -> dict[str, Any]:
    """
    Node 4: Build final workflow result.

    This is not an agent node.
    """

    existing_errors = _state_errors(state)
    new_errors: list[str] = []

    gap_analysis = state.get("gap_analysis")
    resume_revision = state.get("resume_revision")
    final_resume_markdown = state.get("final_resume_markdown")

    if not existing_errors and resume_revision is None:
        new_errors.append("Resume revision result is missing.")

    all_errors = existing_errors + new_errors
    success = not all_errors and resume_revision is not None

    if success:
        status = "success"
        output_summary = "Final workflow result created successfully."
    else:
        status = "error"
        output_summary = "Final workflow result created with errors."

    trace = _trace_step(
        step_number=4,
        step_name="Build Final Output",
        agent_name=None,
        status=status,
        input_summary="Gap analysis, resume revision, workflow trace, and errors.",
        output_summary=output_summary,
        metadata={
            "success": success,
            "error_count": len(all_errors),
        },
    )

    final_trace = list(state.get("agent_trace") or []) + [trace]

    final_output = FinalWorkflowResult(
        success=success,
        gap_analysis=gap_analysis,
        resume_revision=resume_revision,
        final_resume_markdown=final_resume_markdown,
        agent_trace=final_trace,
        errors=all_errors,
    )

    update: dict[str, Any] = {
        "final_output": final_output,
        "agent_trace": [trace],
    }

    if new_errors:
        update["errors"] = new_errors

    return update