from __future__ import annotations

from typing import Any

from src.schemas import AgentTraceStep


def create_trace_step(
    step_number: int,
    step_name: str,
    status: str,
    input_summary: str,
    output_summary: str,
    agent_name: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> AgentTraceStep:
    """
    Create a workflow trace step for UI display.

    Example:
    Step 1: Cleaned inputs
    Step 2: Agent 1 analyzed job-resume gaps
    Step 3: Agent 2 revised resume
    Step 4: Final report generated
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


def trace_to_dict(trace_step: AgentTraceStep) -> dict[str, Any]:
    """
    Convert one trace step into a dictionary for Streamlit tables.
    """

    return {
        "Step": trace_step.step_number,
        "Name": trace_step.step_name,
        "Agent": trace_step.agent_name or "Workflow node",
        "Status": trace_step.status,
        "Input": trace_step.input_summary,
        "Output": trace_step.output_summary,
    }


def trace_to_rows(trace_steps: list[AgentTraceStep]) -> list[dict[str, Any]]:
    """
    Convert a list of trace steps into table rows.
    """

    return [trace_to_dict(step) for step in trace_steps]


def format_trace_as_markdown(trace_steps: list[AgentTraceStep]) -> str:
    """
    Format trace steps as readable Markdown.
    """

    if not trace_steps:
        return "_No workflow trace available._"

    blocks: list[str] = []

    for step in trace_steps:
        agent_label = step.agent_name or "Workflow node"

        blocks.append(
            "\n".join(
                [
                    f"### Step {step.step_number}: {step.step_name}",
                    f"- **Agent:** {agent_label}",
                    f"- **Status:** `{step.status}`",
                    f"- **Input:** {step.input_summary}",
                    f"- **Output:** {step.output_summary}",
                ]
            )
        )

    return "\n\n".join(blocks)