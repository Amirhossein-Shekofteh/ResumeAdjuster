from __future__ import annotations

from typing import Iterable

from src.schemas import (
    FinalWorkflowResult,
    GapAnalysisResult,
    ResumeChange,
    ResumeRevisionResult,
)
from src.utils.formatting import (
    format_change_summary,
    format_fit_score,
    format_gap_table,
    format_keyword_list,
    format_markdown_list,
    format_requirements_table,
    format_warning_list,
)


class ResumeRendererError(ValueError):
    """
    Raised when resume rendering receives invalid input.
    """


def render_updated_resume(
    resume_revision: ResumeRevisionResult | str | None,
) -> str:
    """
    Render the updated resume as Markdown.

    Accepts either:
    - ResumeRevisionResult
    - raw Markdown string
    - None
    """

    if resume_revision is None:
        return "_No updated resume was generated._"

    if isinstance(resume_revision, str):
        markdown = resume_revision.strip()
        return markdown or "_No updated resume was generated._"

    markdown = resume_revision.updated_resume_markdown.strip()
    return markdown or "_No updated resume was generated._"


def render_change_summary(
    resume_revision: ResumeRevisionResult | Iterable[ResumeChange] | None,
) -> str:
    """
    Render a readable summary of resume changes.
    """

    if resume_revision is None:
        return "_No resume changes were generated._"

    if isinstance(resume_revision, ResumeRevisionResult):
        changes = resume_revision.changes
        added_keywords = resume_revision.added_keywords
        removed_items = resume_revision.removed_or_reduced_items
        coursework_evidence = resume_revision.evidence_used_from_coursework
        warnings = resume_revision.warnings
        revision_summary = resume_revision.revision_summary
        decision = resume_revision.decision
    else:
        changes = list(resume_revision)
        added_keywords = []
        removed_items = []
        coursework_evidence = []
        warnings = []
        revision_summary = ""
        decision = "revise"

    if decision != "revise":
        heading = (
            "No Changes Made -- Already Strong"
            if decision == "keep_already_strong"
            else "No Changes Made -- Insufficient Evidence For This Role"
        )
        default_explanation = (
            "The resume already fits this role well; no truthful change would "
            "meaningfully improve it."
            if decision == "keep_already_strong"
            else "There wasn't enough truthful evidence to strengthen the resume "
            "for this role."
        )
        keep_sections = [
            f"## {heading}\n\n" + (revision_summary.strip() or default_explanation)
        ]

        if warnings:
            keep_sections.append("## Warnings\n\n" + format_warning_list(warnings))

        return "\n\n".join(keep_sections).strip()

    sections: list[str] = []

    if revision_summary:
        sections.append("## Revision Summary\n\n" + revision_summary.strip())

    sections.append("## Changes Made\n\n" + format_change_summary(changes))

    if added_keywords:
        sections.append(
            "## Keywords Added Truthfully\n\n"
            + format_keyword_list(added_keywords)
        )

    if removed_items:
        sections.append(
            "## Removed or Reduced Content\n\n"
            + format_markdown_list(removed_items)
        )

    if coursework_evidence:
        sections.append(
            "## Coursework / Student Evidence Used\n\n"
            + format_markdown_list(coursework_evidence)
        )

    if warnings:
        sections.append("## Warnings\n\n" + format_warning_list(warnings))

    return "\n\n".join(sections).strip()


def render_gap_analysis_summary(gap_analysis: GapAnalysisResult | None) -> str:
    """
    Render Agent 1's gap analysis into a compact Markdown summary.
    """

    if gap_analysis is None:
        return "_No gap analysis was generated._"

    sections: list[str] = []

    sections.append(
        "## Target Role Summary\n\n"
        + gap_analysis.target_role_summary.strip()
    )

    sections.append(
        "## Estimated Fit\n\n"
        + format_fit_score(gap_analysis.estimated_fit_score)
    )

    sections.append(
        "## Current Fit Summary\n\n"
        + gap_analysis.overall_fit_summary.strip()
    )

    sections.append(
        "## Extracted Job Requirements\n\n"
        + format_requirements_table(gap_analysis.job_requirements)
    )

    sections.append(
        "## Resume Gaps\n\n"
        + format_gap_table(gap_analysis.gaps)
    )

    if gap_analysis.low_relevance_items:
        low_relevance_lines = [
            (
                f"**{item.resume_section}**: {item.text}  \n"
                f"_Reason_: {item.reason}  \n"
                f"_Recommendation_: `{item.recommendation}`"
            )
            for item in gap_analysis.low_relevance_items
        ]

        sections.append(
            "## Lower-Relevance Resume Content\n\n"
            + format_markdown_list(low_relevance_lines)
        )

    return "\n\n".join(sections).strip()


def render_final_report(final_result: FinalWorkflowResult) -> str:
    """
    Render the full workflow output as a Markdown report.
    """

    if final_result is None:
        raise ResumeRendererError("final_result cannot be None.")

    sections: list[str] = []

    sections.append("# ResumeAdjuster Report")

    if final_result.success:
        sections.append("**Status:** Success")
    else:
        sections.append("**Status:** Completed with errors")

    if final_result.errors:
        sections.append("## Errors\n\n" + format_warning_list(final_result.errors))

    sections.append(
        "# Agent 1 Output: Job-Resume Gap Analysis\n\n"
        + render_gap_analysis_summary(final_result.gap_analysis)
    )

    sections.append(
        "# Agent 2 Output: Resume Revision Summary\n\n"
        + render_change_summary(final_result.resume_revision)
    )

    sections.append(
        "# Updated Resume\n\n"
        + render_updated_resume(
            final_result.final_resume_markdown
            or final_result.resume_revision
        )
    )

    if final_result.agent_trace:
        trace_lines = [
            (
                f"**Step {step.step_number}: {step.step_name}**  \n"
                f"Status: `{step.status}`  \n"
                f"Agent: {step.agent_name or 'Workflow node'}  \n"
                f"Output: {step.output_summary}"
            )
            for step in final_result.agent_trace
        ]

        sections.append("# Workflow Trace\n\n" + format_markdown_list(trace_lines))

    return "\n\n".join(sections).strip()