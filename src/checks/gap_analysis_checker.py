from __future__ import annotations

import re

from src.checks.semantic_check_result import SemanticCheckResult, SemanticStatus
from src.schemas import GapAnalysisResult


def _normalize(text: str | None) -> str:
    """
    Normalize text for stable matching across PDF/DOCX whitespace artifacts.
    """

    return re.sub(r"\s+", " ", text or "").strip().lower()


def _quote_is_present(quote: str, source_text: str) -> bool:
    """
    Return True only when the (normalized) quote appears in the source text.
    """

    normalized_quote = _normalize(quote)

    if not normalized_quote:
        return False

    return normalized_quote in _normalize(source_text)


def run_gap_analysis_semantic_check(
    *,
    gap_analysis: GapAnalysisResult,
    job_description: str,
    current_resume: str,
) -> SemanticCheckResult:
    """
    Validate that Agent 1's gap analysis is grounded in the actual job
    description / resume text and internally consistent.

    Rules:
    1. job_requirements must not be empty.
    2. requirement_id, evidence_id, gap_id, and item_id must each be unique
       within their own collection.
    3. Every requirement_id referenced elsewhere must exist in job_requirements.
    4. Every matched/preserved resume evidence text must appear in the resume.
    5. Every low-relevance item's text must appear in the resume.
    6. (warning) gaps_to_address entries should also appear in the top-level
       gaps list.
    7. (warning) keywords_to_include_if_truthful should appear in the job
       description.
    """

    errors: list[str] = []
    warnings: list[str] = []
    total_checks = 0
    failed_checks = 0

    revision_brief = gap_analysis.revision_brief

    # 1. Non-empty extraction.
    total_checks += 1
    if not gap_analysis.job_requirements:
        failed_checks += 1
        errors.append("Agent 1 returned no job_requirements.")

    requirement_ids = {
        requirement.requirement_id for requirement in gap_analysis.job_requirements
    }

    # 2. Unique IDs, one atomic check per collection.
    def _check_unique(label: str, ids: list[str]) -> None:
        nonlocal total_checks, failed_checks

        total_checks += 1
        seen: set[str] = set()
        duplicates: set[str] = set()

        for item_id in ids:
            if item_id in seen:
                duplicates.add(item_id)
            seen.add(item_id)

        if duplicates:
            failed_checks += 1
            errors.append(
                f"Duplicate {label} ID(s) found: {', '.join(sorted(duplicates))}."
            )

    _check_unique(
        "requirement",
        [requirement.requirement_id for requirement in gap_analysis.job_requirements],
    )
    _check_unique(
        "evidence",
        [evidence.evidence_id for evidence in gap_analysis.matched_resume_evidence],
    )
    _check_unique("gap", [gap.gap_id for gap in gap_analysis.gaps])
    _check_unique(
        "low-relevance item",
        [item.item_id for item in gap_analysis.low_relevance_items],
    )

    # 3. Referential integrity, one atomic check per referenced requirement ID.
    def _check_reference(source: str, referenced_id: str) -> None:
        nonlocal total_checks, failed_checks

        total_checks += 1
        if referenced_id not in requirement_ids:
            failed_checks += 1
            errors.append(
                f"{source} references unknown requirement_id "
                f"{referenced_id!r} (not found in job_requirements)."
            )

    for evidence in gap_analysis.matched_resume_evidence:
        for requirement_id in evidence.supported_requirement_ids:
            _check_reference(
                f"Evidence {evidence.evidence_id}", requirement_id
            )

    for gap in gap_analysis.gaps:
        _check_reference(f"Gap {gap.gap_id}", gap.requirement_id)

    for requirement_id in revision_brief.must_address_requirement_ids:
        _check_reference("revision_brief.must_address_requirement_ids", requirement_id)

    for gap in revision_brief.gaps_to_address:
        _check_reference(
            f"revision_brief.gaps_to_address[{gap.gap_id}]", gap.requirement_id
        )

    # 4. Evidence grounding, one atomic check per evidence item.
    def _check_grounded(source: str, quote: str) -> None:
        nonlocal total_checks, failed_checks

        total_checks += 1
        if not _quote_is_present(quote, current_resume):
            failed_checks += 1
            errors.append(
                f"{source} text was not found in current_resume: {quote!r}."
            )

    for evidence in gap_analysis.matched_resume_evidence:
        _check_grounded(f"Evidence {evidence.evidence_id}", evidence.text)

    for evidence in revision_brief.resume_evidence_to_preserve:
        _check_grounded(
            f"revision_brief.resume_evidence_to_preserve[{evidence.evidence_id}]",
            evidence.text,
        )

    # 5. Low-relevance grounding, one atomic check per item.
    for item in gap_analysis.low_relevance_items:
        _check_grounded(f"Low-relevance item {item.item_id}", item.text)

    # 6. (warning) revision_brief.gaps_to_address should exist in top-level gaps.
    gap_ids = {gap.gap_id for gap in gap_analysis.gaps}
    for gap in revision_brief.gaps_to_address:
        if gap.gap_id not in gap_ids:
            warnings.append(
                f"revision_brief.gaps_to_address includes gap {gap.gap_id!r}, "
                "which does not appear in the top-level gaps list."
            )

    # 7. (warning) keywords_to_include_if_truthful should appear in job_description.
    for keyword in revision_brief.keywords_to_include_if_truthful:
        if not _quote_is_present(keyword, job_description):
            warnings.append(
                f"Keyword {keyword!r} in revision_brief.keywords_to_include_if_truthful "
                "was not found in the job description."
            )

    passed = not errors
    status: SemanticStatus = "fail" if errors else "warning" if warnings else "pass"

    return SemanticCheckResult(
        status=status,
        passed=passed,
        errors=errors,
        warnings=warnings,
        total_checks=total_checks,
        failed_checks=failed_checks,
    )
