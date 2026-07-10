from __future__ import annotations

from operator import add
from typing import Annotated, TypedDict

from src.llm_client import LLMClient
from src.schemas import (
    AgentTraceStep,
    FinalWorkflowResult,
    GapAnalysisResult,
    ResumeRevisionResult,
    RevisionBrief,
)


class ResumeAdjusterState(TypedDict, total=False):
    """
    Shared state passed between LangGraph nodes.

    Raw inputs:
    - job_description
    - current_resume
    - coursework_student_info

    Cleaned inputs:
    - cleaned_job_description
    - cleaned_current_resume
    - cleaned_coursework_student_info

    Agent outputs:
    - gap_analysis
    - revision_brief
    - resume_revision

    Final output:
    - final_resume_markdown
    - final_output

    Trace/debug:
    - errors
    - agent_trace
    """

    job_description: str
    current_resume: str
    coursework_student_info: str
    llm_client: LLMClient | None

    cleaned_job_description: str
    cleaned_current_resume: str
    cleaned_coursework_student_info: str

    gap_analysis: GapAnalysisResult | None
    revision_brief: RevisionBrief | None
    resume_revision: ResumeRevisionResult | None

    final_resume_markdown: str | None
    final_output: FinalWorkflowResult | None

    errors: Annotated[list[str], add]
    agent_trace: Annotated[list[AgentTraceStep], add]


def build_initial_state(
    job_description: str,
    current_resume: str,
    coursework_student_info: str,
    llm_client: LLMClient | None = None,
) -> ResumeAdjusterState:
    """
    Build the initial state for the ResumeAdjuster graph.
    """

    return {
        "job_description": job_description,
        "current_resume": current_resume,
        "coursework_student_info": coursework_student_info,
        "llm_client": llm_client,
        "gap_analysis": None,
        "revision_brief": None,
        "resume_revision": None,
        "final_resume_markdown": None,
        "final_output": None,
        "errors": [],
        "agent_trace": [],
    }