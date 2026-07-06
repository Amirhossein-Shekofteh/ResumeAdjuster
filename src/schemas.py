from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


Priority = Literal["required", "preferred", "nice_to_have"]
GapSeverity = Literal["high", "medium", "low"]
GapType = Literal["missing", "weak", "unclear"]
ChangeType = Literal["add", "remove", "rewrite", "reorder", "keep"]
TraceStatus = Literal["success", "warning", "error"]


class JobRequirement(BaseModel):
    """
    A single requirement extracted from the job description.
    """

    requirement_id: str = Field(
        description="Unique ID for the requirement, such as REQ-001."
    )
    description: str = Field(
        description="Clear description of the job requirement."
    )
    priority: Priority = Field(
        description="Whether the requirement is required, preferred, or nice to have."
    )
    category: str = Field(
        description="Requirement category, such as technical skill, soft skill, tool, experience, education, or domain knowledge."
    )
    keywords: list[str] = Field(
        default_factory=list,
        description="Important keywords related to this requirement."
    )


class ResumeEvidence(BaseModel):
    """
    Evidence found in the current resume that supports one or more job requirements.
    """

    evidence_id: str = Field(
        description="Unique ID for the evidence item, such as EVID-001."
    )
    resume_section: str = Field(
        description="Resume section where the evidence appears, such as Skills, Projects, Experience, or Education."
    )
    text: str = Field(
        description="Exact or near-exact resume content that provides evidence."
    )
    supported_requirement_ids: list[str] = Field(
        default_factory=list,
        description="IDs of job requirements supported by this evidence."
    )
    strength: Literal["strong", "partial", "weak"] = Field(
        description="How strongly this resume evidence supports the requirement."
    )
    explanation: str = Field(
        description="Explanation of why this evidence is relevant."
    )


class GapItem(BaseModel):
    """
    A missing, weak, or unclear area in the current resume compared with the job requirements.
    """

    gap_id: str = Field(
        description="Unique ID for the gap, such as GAP-001."
    )
    requirement_id: str = Field(
        description="ID of the job requirement related to this gap."
    )
    gap_type: GapType = Field(
        description="Whether the gap is missing, weak, or unclear."
    )
    severity: GapSeverity = Field(
        description="How important this gap is for the target job."
    )
    description: str = Field(
        description="Description of the resume gap."
    )
    why_it_matters: str = Field(
        description="Why this gap matters for the target job."
    )
    suggested_evidence_to_search_for: list[str] = Field(
        default_factory=list,
        description="Types of coursework, projects, tools, or experience Agent 2 should look for in the student's background information."
    )


class LowRelevanceItem(BaseModel):
    """
    Resume content that may be less relevant to the target job and could be reduced or replaced.
    """

    item_id: str = Field(
        description="Unique ID for the low-relevance item, such as LOW-001."
    )
    resume_section: str = Field(
        description="Resume section where this item appears."
    )
    text: str = Field(
        description="Resume content that may be less relevant for this job."
    )
    reason: str = Field(
        description="Why this content is less relevant to the target job."
    )
    recommendation: Literal["remove", "shorten", "move_lower", "keep_if_space"] = Field(
        description="Recommended treatment for this item."
    )


class RevisionBrief(BaseModel):
    """
    Structured handoff from Agent 1 to Agent 2.

    Agent 2 should use this brief instead of re-reading the full job description.
    """

    target_role_summary: str = Field(
        description="Short summary of the target role based on Agent 1's job analysis."
    )
    must_address_requirement_ids: list[str] = Field(
        default_factory=list,
        description="High-priority requirement IDs that Agent 2 should try to address."
    )
    keywords_to_include_if_truthful: list[str] = Field(
        default_factory=list,
        description="Job-relevant keywords that should only be added if supported by resume or student background evidence."
    )
    gaps_to_address: list[GapItem] = Field(
        default_factory=list,
        description="Specific gaps Agent 2 should try to fill using coursework or student background information."
    )
    resume_evidence_to_preserve: list[ResumeEvidence] = Field(
        default_factory=list,
        description="Relevant existing resume evidence that should remain in the revised resume."
    )
    low_relevance_items_to_reduce: list[LowRelevanceItem] = Field(
        default_factory=list,
        description="Resume items that may be reduced or replaced if stronger relevant evidence exists."
    )
    instructions_for_revision_agent: list[str] = Field(
        default_factory=list,
        description="Specific editing instructions for Agent 2."
    )


class GapAnalysisResult(BaseModel):
    """
    Output from Agent 1: Job-Resume Gap Analyst.
    """

    target_role_summary: str = Field(
        description="Concise summary of what the job is looking for."
    )
    job_requirements: list[JobRequirement] = Field(
        default_factory=list,
        description="Structured list of requirements extracted from the job description."
    )
    matched_resume_evidence: list[ResumeEvidence] = Field(
        default_factory=list,
        description="Resume evidence that already supports the target job."
    )
    gaps: list[GapItem] = Field(
        default_factory=list,
        description="Missing, weak, or unclear areas in the resume."
    )
    low_relevance_items: list[LowRelevanceItem] = Field(
        default_factory=list,
        description="Resume items that may be less relevant to the target job."
    )
    revision_brief: RevisionBrief = Field(
        description="Structured handoff for Agent 2."
    )
    overall_fit_summary: str = Field(
        description="Plain-language summary of how well the resume currently fits the job."
    )
    estimated_fit_score: int = Field(
        ge=0,
        le=100,
        description="Estimated resume-job fit score from 0 to 100."
    )


class ResumeChange(BaseModel):
    """
    A single change made or recommended by Agent 2.
    """

    change_id: str = Field(
        description="Unique ID for the change, such as CHG-001."
    )
    change_type: ChangeType = Field(
        description="Type of resume change."
    )
    resume_section: str = Field(
        description="Resume section affected by the change."
    )
    before: str | None = Field(
        default=None,
        description="Original resume content, if applicable."
    )
    after: str | None = Field(
        default=None,
        description="Updated resume content, if applicable."
    )
    reason: str = Field(
        description="Why this change improves alignment with the target job."
    )
    evidence_source: str = Field(
        description="Where the supporting evidence came from, such as original resume, coursework info, project info, or Agent 1 revision brief."
    )


class ResumeRevisionResult(BaseModel):
    """
    Output from Agent 2: Resume Revision Agent.
    """

    updated_resume_markdown: str = Field(
        description="The full revised resume in Markdown format."
    )
    changes: list[ResumeChange] = Field(
        default_factory=list,
        description="List of changes made to the resume."
    )
    added_keywords: list[str] = Field(
        default_factory=list,
        description="Keywords added to the resume because they were truthfully supported."
    )
    removed_or_reduced_items: list[str] = Field(
        default_factory=list,
        description="Resume items removed, shortened, or de-emphasized."
    )
    evidence_used_from_coursework: list[str] = Field(
        default_factory=list,
        description="Coursework or student background evidence used in the revision."
    )
    warnings: list[str] = Field(
        default_factory=list,
        description="Warnings about gaps that could not be filled truthfully."
    )
    revision_summary: str = Field(
        description="Plain-language explanation of the resume revision."
    )


class AgentTraceStep(BaseModel):
    """
    A lightweight trace step for showing the agentic workflow in the UI.
    """

    step_number: int = Field(
        ge=1,
        description="Sequential step number."
    )
    step_name: str = Field(
        description="Name of the workflow step."
    )
    agent_name: str | None = Field(
        default=None,
        description="Name of the agent responsible for this step, if applicable."
    )
    status: TraceStatus = Field(
        description="Whether the step succeeded, produced a warning, or failed."
    )
    input_summary: str = Field(
        description="Short summary of the input used in this step."
    )
    output_summary: str = Field(
        description="Short summary of the output produced in this step."
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Optional extra details for debugging or display."
    )


class FinalWorkflowResult(BaseModel):
    """
    Final result returned by the LangGraph workflow.
    """

    success: bool = Field(
        description="Whether the full workflow completed successfully."
    )
    gap_analysis: GapAnalysisResult | None = Field(
        default=None,
        description="Agent 1 result."
    )
    resume_revision: ResumeRevisionResult | None = Field(
        default=None,
        description="Agent 2 result."
    )
    final_resume_markdown: str | None = Field(
        default=None,
        description="Final updated resume in Markdown format."
    )
    agent_trace: list[AgentTraceStep] = Field(
        default_factory=list,
        description="Trace of workflow steps for UI display."
    )
    errors: list[str] = Field(
        default_factory=list,
        description="Errors encountered during the workflow."
    )