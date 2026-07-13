from __future__ import annotations

from src.schemas import GapAnalysisResult


PRIORITY_WEIGHTS: dict[str, float] = {
    "required": 3.0,
    "preferred": 2.0,
    "nice_to_have": 1.0,
}

EVIDENCE_STRENGTH_SCORES: dict[str, float] = {
    "strong": 1.0,
    "partial": 0.6,
    "weak": 0.3,
}

GAP_SEVERITY_PENALTIES: dict[str, float] = {
    "high": 0.6,
    "medium": 0.35,
    "low": 0.15,
}


def compute_fit_score(gap_analysis: GapAnalysisResult) -> int:
    """
    Compute a deterministic resume-job fit score from Agent 1's structured
    requirements, evidence, and gaps, instead of trusting the LLM's own
    freeform 0-100 guess.

    Each requirement's coverage is the strength of its best matching evidence,
    reduced by the worst gap penalty against it, then weighted by priority.
    """

    if not gap_analysis.job_requirements:
        return gap_analysis.estimated_fit_score

    best_strength_by_requirement: dict[str, float] = {}
    for evidence in gap_analysis.matched_resume_evidence:
        strength_score = EVIDENCE_STRENGTH_SCORES.get(evidence.strength, 0.0)
        for requirement_id in evidence.supported_requirement_ids:
            best_strength_by_requirement[requirement_id] = max(
                best_strength_by_requirement.get(requirement_id, 0.0),
                strength_score,
            )

    worst_penalty_by_requirement: dict[str, float] = {}
    for gap in gap_analysis.gaps:
        penalty = GAP_SEVERITY_PENALTIES.get(gap.severity, 0.0)
        worst_penalty_by_requirement[gap.requirement_id] = max(
            worst_penalty_by_requirement.get(gap.requirement_id, 0.0),
            penalty,
        )

    weighted_coverage_sum = 0.0
    weight_sum = 0.0

    for requirement in gap_analysis.job_requirements:
        weight = PRIORITY_WEIGHTS.get(requirement.priority, 1.0)
        coverage = best_strength_by_requirement.get(requirement.requirement_id, 0.0)
        coverage -= worst_penalty_by_requirement.get(requirement.requirement_id, 0.0)
        coverage = max(0.0, min(1.0, coverage))

        weighted_coverage_sum += weight * coverage
        weight_sum += weight

    score = round(100 * weighted_coverage_sum / weight_sum)
    return max(0, min(100, score))
