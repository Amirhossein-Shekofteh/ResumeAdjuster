from __future__ import annotations

from src.schemas import (
    GapAnalysisResult,
    GapItem,
    JobRequirement,
    ResumeEvidence,
    RevisionBrief,
)
from src.scoring import compute_fit_score


def _requirement(requirement_id: str, priority: str) -> JobRequirement:
    return JobRequirement(
        requirement_id=requirement_id,
        description=f"Requirement {requirement_id}",
        priority=priority,
        category="technical skill",
        keywords=[],
    )


def _evidence(evidence_id: str, requirement_id: str, strength: str) -> ResumeEvidence:
    return ResumeEvidence(
        evidence_id=evidence_id,
        resume_section="Experience",
        text="Evidence text.",
        supported_requirement_ids=[requirement_id],
        strength=strength,
        explanation="Explanation.",
    )


def _gap(gap_id: str, requirement_id: str, severity: str) -> GapItem:
    return GapItem(
        gap_id=gap_id,
        requirement_id=requirement_id,
        gap_type="missing",
        severity=severity,
        description="Gap description.",
        why_it_matters="It matters.",
        suggested_evidence_to_search_for=[],
    )


def _empty_revision_brief() -> RevisionBrief:
    return RevisionBrief(
        target_role_summary="Role summary.",
        must_address_requirement_ids=[],
        keywords_to_include_if_truthful=[],
        gaps_to_address=[],
        resume_evidence_to_preserve=[],
        low_relevance_items_to_reduce=[],
        instructions_for_revision_agent=[],
    )


def _gap_analysis(
    job_requirements: list[JobRequirement],
    matched_resume_evidence: list[ResumeEvidence],
    gaps: list[GapItem],
    estimated_fit_score: int = 50,
) -> GapAnalysisResult:
    return GapAnalysisResult(
        target_role_summary="Role summary.",
        job_requirements=job_requirements,
        matched_resume_evidence=matched_resume_evidence,
        gaps=gaps,
        low_relevance_items=[],
        revision_brief=_empty_revision_brief(),
        overall_fit_summary="Summary.",
        estimated_fit_score=estimated_fit_score,
    )


def test_all_required_requirements_strongly_matched_scores_100() -> None:
    requirements = [
        _requirement("REQ-001", "required"),
        _requirement("REQ-002", "required"),
    ]
    evidence = [
        _evidence("EVID-001", "REQ-001", "strong"),
        _evidence("EVID-002", "REQ-002", "strong"),
    ]

    gap_analysis = _gap_analysis(requirements, evidence, gaps=[])

    assert compute_fit_score(gap_analysis) == 100


def test_all_required_requirements_missing_with_high_severity_gaps_scores_0() -> None:
    requirements = [
        _requirement("REQ-001", "required"),
        _requirement("REQ-002", "required"),
    ]
    gaps = [
        _gap("GAP-001", "REQ-001", "high"),
        _gap("GAP-002", "REQ-002", "high"),
    ]

    gap_analysis = _gap_analysis(requirements, matched_resume_evidence=[], gaps=gaps)

    assert compute_fit_score(gap_analysis) == 0


def test_mixed_required_and_preferred_weighting() -> None:
    requirements = [
        _requirement("REQ-001", "required"),
        _requirement("REQ-002", "required"),
        _requirement("REQ-003", "required"),
        _requirement("REQ-004", "preferred"),
        _requirement("REQ-005", "preferred"),
    ]
    evidence = [
        _evidence("EVID-001", "REQ-001", "strong"),
        _evidence("EVID-002", "REQ-002", "strong"),
        _evidence("EVID-003", "REQ-004", "partial"),
        _evidence("EVID-004", "REQ-005", "partial"),
    ]
    gaps = [_gap("GAP-001", "REQ-003", "high")]

    gap_analysis = _gap_analysis(requirements, evidence, gaps)

    # weights: 3,3,3,2,2 = 13; coverage: 1,1,0,0.6,0.6
    # weighted sum = 3+3+0+1.2+1.2 = 8.4 -> 8.4/13*100 = 64.6 -> 65
    assert compute_fit_score(gap_analysis) == 65


def test_empty_job_requirements_falls_back_to_llm_score() -> None:
    gap_analysis = _gap_analysis([], [], [], estimated_fit_score=42)

    assert compute_fit_score(gap_analysis) == 42
