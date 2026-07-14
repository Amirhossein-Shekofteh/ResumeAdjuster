from __future__ import annotations

from typing import Any, Iterator

from src.graph.builder import build_resume_adjuster_graph
from src.graph.state import ResumeAdjusterState, build_initial_state
from src.llm_client import LLMClient
from src.schemas import AgentTraceStep, FinalWorkflowResult


def _fallback_error_result(error_message: str) -> FinalWorkflowResult:
    """
    Build a safe FinalWorkflowResult if the graph fails before final_output_node.
    """

    trace = AgentTraceStep(
        step_number=1,
        step_name="Run Workflow",
        agent_name=None,
        status="error",
        input_summary="Job description, current resume, and coursework/student information.",
        output_summary=error_message,
        metadata={},
    )

    return FinalWorkflowResult(
        success=False,
        gap_analysis=None,
        resume_revision=None,
        final_resume_markdown=None,
        agent_trace=[trace],
        errors=[error_message],
    )


def _coerce_final_output(value: Any) -> FinalWorkflowResult | None:
    """
    Convert the final_output state value into FinalWorkflowResult if possible.
    """

    if value is None:
        return None

    if isinstance(value, FinalWorkflowResult):
        return value

    if isinstance(value, dict):
        return FinalWorkflowResult.model_validate(value)

    raise TypeError(
        f"final_output must be FinalWorkflowResult, dict, or None. Got {type(value).__name__}."
    )


def _finalize_result_state(result_state: ResumeAdjusterState) -> FinalWorkflowResult:
    """
    Convert a completed graph state into a FinalWorkflowResult.
    """

    final_output = _coerce_final_output(result_state.get("final_output"))

    if final_output is not None:
        return final_output

    return FinalWorkflowResult(
        success=False,
        gap_analysis=result_state.get("gap_analysis"),
        resume_revision=result_state.get("resume_revision"),
        final_resume_markdown=result_state.get("final_resume_markdown"),
        agent_trace=list(result_state.get("agent_trace") or []),
        errors=list(result_state.get("errors") or [])
        + ["Workflow completed without producing final_output."],
    )


def run_resume_adjuster(
    job_description: str,
    current_resume: str,
    coursework_student_info: str,
    llm_client: LLMClient | None = None,
) -> FinalWorkflowResult:
    """
    Run the full ResumeAdjuster graph.

    This is the main function that app.py should call.
    """

    initial_state = build_initial_state(
        job_description=job_description,
        current_resume=current_resume,
        coursework_student_info=coursework_student_info,
        llm_client=llm_client,
    )

    try:
        graph = build_resume_adjuster_graph()
        result_state: ResumeAdjusterState = graph.invoke(initial_state)

        return _finalize_result_state(result_state)

    except Exception as exc:
        return _fallback_error_result(f"ResumeAdjuster workflow failed: {exc}")


def stream_resume_adjuster(
    job_description: str,
    current_resume: str,
    coursework_student_info: str,
    llm_client: LLMClient | None = None,
) -> Iterator[list[AgentTraceStep] | FinalWorkflowResult]:
    """
    Run the full ResumeAdjuster graph, yielding the growing agent_trace after
    each node completes, then yielding the final FinalWorkflowResult.

    This is what app.py should call to show a live, node-level progress
    tracker while the workflow is running.
    """

    initial_state = build_initial_state(
        job_description=job_description,
        current_resume=current_resume,
        coursework_student_info=coursework_student_info,
        llm_client=llm_client,
    )

    try:
        graph = build_resume_adjuster_graph()
        result_state: ResumeAdjusterState = initial_state

        for result_state in graph.stream(initial_state, stream_mode="values"):
            yield list(result_state.get("agent_trace") or [])

        yield _finalize_result_state(result_state)

    except Exception as exc:
        yield _fallback_error_result(f"ResumeAdjuster workflow failed: {exc}")