from __future__ import annotations

from operator import add
from typing import Annotated, TypedDict

from src.checks.semantic_check_result import SemanticCheckResult
from src.llm_client import LLMClient
from src.schemas import (
    AgentTraceStep,
    FinalWorkflowResult,
    GapAnalysisResult,
    ResumeRevisionResult,
    RevisionBrief,
    ReviewGateResult,
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

    Semantic check / repair loop (Agent 1):
    - gap_analysis_semantic_check
    - gap_analysis_repair_attempts

    Semantic check / repair loop (Agent 2):
    - resume_revision_semantic_check
    - resume_revision_repair_attempts

    Reviewer gates (scope/boundary checks):
    - agent1_review_gate
    - agent2_review_gate

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

    gap_analysis_semantic_check: SemanticCheckResult | None
    gap_analysis_repair_attempts: int

    resume_revision_semantic_check: SemanticCheckResult | None
    resume_revision_repair_attempts: int

    agent1_review_gate: ReviewGateResult | None
    agent2_review_gate: ReviewGateResult | None

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
        "gap_analysis_semantic_check": None,
        "gap_analysis_repair_attempts": 0,
        "resume_revision_semantic_check": None,
        "resume_revision_repair_attempts": 0,
        "agent1_review_gate": None,
        "agent2_review_gate": None,
        "final_resume_markdown": None,
        "final_output": None,
        "errors": [],
        "agent_trace": [],
    }