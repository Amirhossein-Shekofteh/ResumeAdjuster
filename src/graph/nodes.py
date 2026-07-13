from __future__ import annotations

from typing import Any, Literal

from src.agents.gap_analyst_agent import run_gap_analysis, run_gap_analysis_repair
from src.agents.resume_revision_agent import (
    run_resume_revision,
    run_resume_revision_repair,
)
from src.checks.gap_analysis_checker import run_gap_analysis_semantic_check
from src.checks.resume_revision_checker import (
    finalize_unsupported_resume_revision,
    run_resume_revision_semantic_check,
)
from src.checks.semantic_check_result import compute_semantic_confidence
from src.graph.state import ResumeAdjusterState
from src.schemas import AgentTraceStep, FinalWorkflowResult
from src.text_cleaner import (
    clean_coursework_text,
    clean_job_description_text,
    clean_resume_text,
)


MAX_GAP_ANALYSIS_REPAIR_ATTEMPTS = 3
MAX_RESUME_REVISION_REPAIR_ATTEMPTS = 3


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
            llm_client=state.get("llm_client"),
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


def semantic_check_node(state: ResumeAdjusterState) -> dict[str, Any]:
    """
    Node 3: Deterministic semantic check on Agent 1's output.

    Runs a non-LLM grounding/referential-integrity check on the current
    gap_analysis. On every run (first pass or after a repair) it also
    computes a deterministic confidence score and attaches it, along with any
    unresolved errors/warnings, to the revision_brief that will eventually
    reach Agent 2 -- regardless of whether this particular check passes.
    """

    if _has_errors(state):
        trace = _trace_step(
            step_number=3,
            step_name="Semantic Check",
            agent_name=None,
            status="warning",
            input_summary="Skipped because previous workflow errors exist.",
            output_summary="Semantic check was not run.",
        )

        return {"agent_trace": [trace]}

    gap_analysis = state.get("gap_analysis")
    cleaned_job_description = _required_text(state, "cleaned_job_description")
    cleaned_current_resume = _required_text(state, "cleaned_current_resume")

    if gap_analysis is None:
        raise ValueError("Missing gap_analysis from Agent 1.")

    check = run_gap_analysis_semantic_check(
        gap_analysis=gap_analysis,
        job_description=cleaned_job_description,
        current_resume=cleaned_current_resume,
    )

    confidence = compute_semantic_confidence(check)
    updated_revision_brief = gap_analysis.revision_brief.model_copy(
        update={
            "gap_analysis_confidence": confidence,
            "gap_analysis_semantic_warnings": check.errors + check.warnings,
        }
    )
    updated_gap_analysis = gap_analysis.model_copy(
        update={"revision_brief": updated_revision_brief}
    )

    trace_status = "success" if check.status == "pass" else (
        "warning" if check.status == "warning" else "error"
    )

    trace = _trace_step(
        step_number=3,
        step_name="Semantic Check",
        agent_name=None,
        status=trace_status,
        input_summary="Agent 1's gap analysis, cleaned job description, and cleaned resume.",
        output_summary=(
            f"Semantic check {check.status} "
            f"({len(check.errors)} error(s), {len(check.warnings)} warning(s)); "
            f"confidence {confidence}/100."
        ),
        metadata={
            "status": check.status,
            "error_count": len(check.errors),
            "warning_count": len(check.warnings),
            "confidence": confidence,
        },
    )

    return {
        "gap_analysis": updated_gap_analysis,
        "revision_brief": updated_revision_brief,
        "gap_analysis_semantic_check": check,
        "agent_trace": [trace],
    }


def gap_analysis_repair_node(state: ResumeAdjusterState) -> dict[str, Any]:
    """
    Node 4: Ask Agent 1 to repair a gap analysis that failed semantic check.
    """

    if _has_errors(state):
        trace = _trace_step(
            step_number=4,
            step_name="Gap Analysis Repair",
            agent_name="Job-Resume Gap Analyst",
            status="warning",
            input_summary="Skipped because previous workflow errors exist.",
            output_summary="Gap analysis repair was not run.",
        )

        return {"agent_trace": [trace]}

    try:
        cleaned_job_description = _required_text(state, "cleaned_job_description")
        cleaned_current_resume = _required_text(state, "cleaned_current_resume")

        gap_analysis = state.get("gap_analysis")
        check = state.get("gap_analysis_semantic_check")

        if gap_analysis is None:
            raise ValueError("Missing gap_analysis from Agent 1.")

        if check is None:
            raise ValueError("Missing gap_analysis_semantic_check result.")

        attempts = state.get("gap_analysis_repair_attempts", 0) + 1

        repaired_gap_analysis = run_gap_analysis_repair(
            job_description=cleaned_job_description,
            current_resume=cleaned_current_resume,
            previous_result=gap_analysis,
            validation_errors=check.errors,
            llm_client=state.get("llm_client"),
        )

        trace = _trace_step(
            step_number=4,
            step_name="Gap Analysis Repair",
            agent_name="Job-Resume Gap Analyst",
            status="success",
            input_summary="Previous gap analysis and its semantic validation errors.",
            output_summary=f"Produced repair attempt {attempts}/{MAX_GAP_ANALYSIS_REPAIR_ATTEMPTS}.",
            metadata={"attempt": attempts},
        )

        return {
            "gap_analysis": repaired_gap_analysis,
            "revision_brief": repaired_gap_analysis.revision_brief,
            "gap_analysis_repair_attempts": attempts,
            "agent_trace": [trace],
        }

    except Exception as exc:
        error_message = f"Gap analysis repair failed: {exc}"

        trace = _trace_step(
            step_number=4,
            step_name="Gap Analysis Repair",
            agent_name="Job-Resume Gap Analyst",
            status="error",
            input_summary="Previous gap analysis and its semantic validation errors.",
            output_summary=error_message,
        )

        return {
            "errors": [error_message],
            "agent_trace": [trace],
        }


def route_after_semantic_check(
    state: ResumeAdjusterState,
) -> Literal["resume_revision", "gap_analysis_repair"]:
    """
    Decide whether to proceed to Agent 2 or send Agent 1's output back for repair.

    Never halts the workflow: once repair attempts are exhausted, the
    semantic_check_node has already attached the (possibly low) confidence
    score and warnings to the revision_brief, so we proceed to Agent 2 anyway.
    """

    if _has_errors(state):
        return "resume_revision"

    check = state.get("gap_analysis_semantic_check")

    if check is None or check.passed:
        return "resume_revision"

    attempts = state.get("gap_analysis_repair_attempts", 0)

    if attempts < MAX_GAP_ANALYSIS_REPAIR_ATTEMPTS:
        return "gap_analysis_repair"

    return "resume_revision"


def resume_revision_node(state: ResumeAdjusterState) -> dict[str, Any]:
    """
    Node 5: Run Agent 2.

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
            step_number=5,
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
            llm_client=state.get("llm_client"),
        )

        trace = _trace_step(
            step_number=5,
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
            step_number=5,
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


def resume_revision_semantic_check_node(state: ResumeAdjusterState) -> dict[str, Any]:
    """
    Node 6: Deterministic semantic check on Agent 2's output.

    Unlike Agent 1's checker, truthfulness failures here (an unsupported
    added keyword, an unverifiable coursework claim) are hard errors, not
    warnings: a fabricated credential on a resume is a real harm. On every
    run it also computes a confidence score and attaches it, along with any
    unresolved errors, to resume_revision -- this never touches `errors`,
    since a failing check here may still be repaired or auto-stripped.
    """

    if _has_errors(state):
        trace = _trace_step(
            step_number=6,
            step_name="Resume Revision Semantic Check",
            agent_name=None,
            status="warning",
            input_summary="Skipped because previous workflow errors exist.",
            output_summary="Semantic check was not run.",
        )

        return {"agent_trace": [trace]}

    resume_revision = state.get("resume_revision")
    cleaned_current_resume = _required_text(state, "cleaned_current_resume")
    cleaned_coursework_student_info = _required_text(
        state, "cleaned_coursework_student_info"
    )

    if resume_revision is None:
        raise ValueError("Missing resume_revision from Agent 2.")

    check = run_resume_revision_semantic_check(
        resume_revision=resume_revision,
        current_resume=cleaned_current_resume,
        coursework_student_info=cleaned_coursework_student_info,
    )

    confidence = compute_semantic_confidence(check)
    updated_resume_revision = resume_revision.model_copy(
        update={
            "semantic_confidence": confidence,
            "semantic_warnings": check.errors + check.warnings,
        }
    )

    trace_status = "success" if check.status == "pass" else (
        "warning" if check.status == "warning" else "error"
    )

    trace = _trace_step(
        step_number=6,
        step_name="Resume Revision Semantic Check",
        agent_name=None,
        status=trace_status,
        input_summary="Agent 2's resume revision, cleaned resume, and cleaned coursework info.",
        output_summary=(
            f"Semantic check {check.status} "
            f"({len(check.errors)} error(s), {len(check.warnings)} warning(s)); "
            f"confidence {confidence}/100."
        ),
        metadata={
            "status": check.status,
            "error_count": len(check.errors),
            "warning_count": len(check.warnings),
            "confidence": confidence,
        },
    )

    return {
        "resume_revision": updated_resume_revision,
        "final_resume_markdown": updated_resume_revision.updated_resume_markdown,
        "resume_revision_semantic_check": check,
        "agent_trace": [trace],
    }


def resume_revision_repair_node(state: ResumeAdjusterState) -> dict[str, Any]:
    """
    Node 7: Ask Agent 2 to repair a resume revision that failed semantic check.
    """

    if _has_errors(state):
        trace = _trace_step(
            step_number=7,
            step_name="Resume Revision Repair",
            agent_name="Resume Revision Agent",
            status="warning",
            input_summary="Skipped because previous workflow errors exist.",
            output_summary="Resume revision repair was not run.",
        )

        return {"agent_trace": [trace]}

    try:
        cleaned_current_resume = _required_text(state, "cleaned_current_resume")
        cleaned_coursework_student_info = _required_text(
            state, "cleaned_coursework_student_info"
        )

        resume_revision = state.get("resume_revision")
        check = state.get("resume_revision_semantic_check")
        revision_brief = state.get("revision_brief")

        if resume_revision is None:
            raise ValueError("Missing resume_revision from Agent 2.")

        if check is None:
            raise ValueError("Missing resume_revision_semantic_check result.")

        if revision_brief is None:
            raise ValueError("Missing revision_brief from Agent 1.")

        attempts = state.get("resume_revision_repair_attempts", 0) + 1

        repaired_resume_revision = run_resume_revision_repair(
            current_resume=cleaned_current_resume,
            coursework_student_info=cleaned_coursework_student_info,
            revision_brief=revision_brief,
            previous_result=resume_revision,
            validation_errors=check.errors,
            llm_client=state.get("llm_client"),
        )

        trace = _trace_step(
            step_number=7,
            step_name="Resume Revision Repair",
            agent_name="Resume Revision Agent",
            status="success",
            input_summary="Previous resume revision and its semantic validation errors.",
            output_summary=(
                f"Produced repair attempt {attempts}/{MAX_RESUME_REVISION_REPAIR_ATTEMPTS}."
            ),
            metadata={"attempt": attempts},
        )

        return {
            "resume_revision": repaired_resume_revision,
            "final_resume_markdown": repaired_resume_revision.updated_resume_markdown,
            "resume_revision_repair_attempts": attempts,
            "agent_trace": [trace],
        }

    except Exception as exc:
        error_message = f"Resume revision repair failed: {exc}"

        trace = _trace_step(
            step_number=7,
            step_name="Resume Revision Repair",
            agent_name="Resume Revision Agent",
            status="error",
            input_summary="Previous resume revision and its semantic validation errors.",
            output_summary=error_message,
        )

        return {
            "errors": [error_message],
            "agent_trace": [trace],
        }


def resume_revision_finalize_node(state: ResumeAdjusterState) -> dict[str, Any]:
    """
    Node 8: Deterministically strip unsupported content from Agent 2's output.

    Only reached once repair attempts are exhausted and the check still
    fails. No LLM call: mechanically reverts/removes exactly the content that
    still fails validation, and records every auto-edit as a visible change
    (see finalize_unsupported_resume_revision) so nothing is silently dropped.
    """

    if _has_errors(state):
        trace = _trace_step(
            step_number=8,
            step_name="Resume Revision Finalize",
            agent_name=None,
            status="warning",
            input_summary="Skipped because previous workflow errors exist.",
            output_summary="Finalization was not run.",
        )

        return {"agent_trace": [trace]}

    resume_revision = state.get("resume_revision")
    cleaned_current_resume = _required_text(state, "cleaned_current_resume")
    cleaned_coursework_student_info = _required_text(
        state, "cleaned_coursework_student_info"
    )

    if resume_revision is None:
        raise ValueError("Missing resume_revision from Agent 2.")

    finalized_resume_revision = finalize_unsupported_resume_revision(
        resume_revision=resume_revision,
        current_resume=cleaned_current_resume,
        coursework_student_info=cleaned_coursework_student_info,
    )

    trace = _trace_step(
        step_number=8,
        step_name="Resume Revision Finalize",
        agent_name=None,
        status="warning",
        input_summary=(
            "Resume revision that still failed semantic validation after "
            f"{MAX_RESUME_REVISION_REPAIR_ATTEMPTS} repair attempts."
        ),
        output_summary=(
            "Deterministically stripped unsupported content; final confidence "
            f"{finalized_resume_revision.semantic_confidence}/100."
        ),
        metadata={
            "confidence": finalized_resume_revision.semantic_confidence,
            "semantic_warning_count": len(finalized_resume_revision.semantic_warnings),
        },
    )

    return {
        "resume_revision": finalized_resume_revision,
        "final_resume_markdown": finalized_resume_revision.updated_resume_markdown,
        "agent_trace": [trace],
    }


def route_after_resume_revision_semantic_check(
    state: ResumeAdjusterState,
) -> Literal["final_output", "resume_revision_repair", "resume_revision_finalize"]:
    """
    Decide whether to finish, repair Agent 2's output, or deterministically
    strip unsupported content once repair attempts are exhausted.
    """

    if _has_errors(state):
        return "final_output"

    check = state.get("resume_revision_semantic_check")

    if check is None or check.passed:
        return "final_output"

    attempts = state.get("resume_revision_repair_attempts", 0)

    if attempts < MAX_RESUME_REVISION_REPAIR_ATTEMPTS:
        return "resume_revision_repair"

    return "resume_revision_finalize"


def final_output_node(state: ResumeAdjusterState) -> dict[str, Any]:
    """
    Node 9: Build final workflow result.

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
        step_number=9,
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