from __future__ import annotations

from src.checks.gap_analysis_checker import run_gap_analysis_semantic_check
from src.checks.semantic_check_result import compute_semantic_confidence
from src.schemas import (
    GapAnalysisResult,
    GapItem,
    JobRequirement,
    LowRelevanceItem,
    ResumeEvidence,
    RevisionBrief,
)


JOB_DESCRIPTION = "We need a Python developer with strong data analysis skills."
CURRENT_RESUME = (
    "Built a Python project for analyzing student survey data. "
    "Completed general coursework projects."
)


def _valid_evidence() -> ResumeEvidence:
    return ResumeEvidence(
        evidence_id="EVID-001",
        resume_section="Projects",
        text="Built a Python project for analyzing student survey data.",
        supported_requirement_ids=["REQ-001"],
        strength="strong",
        explanation="Directly supports the Python requirement.",
    )


def _valid_revision_brief(evidence: ResumeEvidence) -> RevisionBrief:
    return RevisionBrief(
        target_role_summary="Entry-level Python data analyst role.",
        must_address_requirement_ids=["REQ-001"],
        keywords_to_include_if_truthful=["Python"],
        gaps_to_address=[],
        resume_evidence_to_preserve=[evidence],
        low_relevance_items_to_reduce=[],
        instructions_for_revision_agent=["Emphasize the Python project."],
    )


def _valid_gap_analysis() -> GapAnalysisResult:
    evidence = _valid_evidence()

    return GapAnalysisResult(
        target_role_summary="Entry-level Python data analyst role.",
        job_requirements=[
            JobRequirement(
                requirement_id="REQ-001",
                description="Experience with Python for data analysis.",
                priority="required",
                category="technical skill",
                keywords=["Python"],
            )
        ],
        matched_resume_evidence=[evidence],
        gaps=[],
        low_relevance_items=[],
        revision_brief=_valid_revision_brief(evidence),
        overall_fit_summary="Good fit.",
        estimated_fit_score=80,
    )


def test_valid_gap_analysis_passes_with_full_confidence() -> None:
    check = run_gap_analysis_semantic_check(
        gap_analysis=_valid_gap_analysis(),
        job_description=JOB_DESCRIPTION,
        current_resume=CURRENT_RESUME,
    )

    assert check.status == "pass"
    assert check.passed is True
    assert check.errors == []
    assert check.warnings == []
    assert compute_semantic_confidence(check) == 100


def test_ungrounded_evidence_text_fails() -> None:
    gap_analysis = _valid_gap_analysis()
    ungrounded_evidence = gap_analysis.matched_resume_evidence[0].model_copy(
        update={"text": "Led a team of ten engineers at a Fortune 500 company."}
    )
    gap_analysis = gap_analysis.model_copy(
        update={"matched_resume_evidence": [ungrounded_evidence]}
    )

    check = run_gap_analysis_semantic_check(
        gap_analysis=gap_analysis,
        job_description=JOB_DESCRIPTION,
        current_resume=CURRENT_RESUME,
    )

    assert check.passed is False
    assert check.status == "fail"
    assert any("was not found in current_resume" in error for error in check.errors)
    assert compute_semantic_confidence(check) < 100


def test_dangling_requirement_reference_fails() -> None:
    gap_analysis = _valid_gap_analysis()
    dangling_evidence = gap_analysis.matched_resume_evidence[0].model_copy(
        update={"supported_requirement_ids": ["REQ-999"]}
    )
    gap_analysis = gap_analysis.model_copy(
        update={"matched_resume_evidence": [dangling_evidence]}
    )

    check = run_gap_analysis_semantic_check(
        gap_analysis=gap_analysis,
        job_description=JOB_DESCRIPTION,
        current_resume=CURRENT_RESUME,
    )

    assert check.passed is False
    assert any("unknown requirement_id" in error for error in check.errors)
    assert compute_semantic_confidence(check) < 100


def test_duplicate_requirement_ids_fail() -> None:
    gap_analysis = _valid_gap_analysis()
    duplicated_requirement = gap_analysis.job_requirements[0]
    gap_analysis = gap_analysis.model_copy(
        update={"job_requirements": [duplicated_requirement, duplicated_requirement]}
    )

    check = run_gap_analysis_semantic_check(
        gap_analysis=gap_analysis,
        job_description=JOB_DESCRIPTION,
        current_resume=CURRENT_RESUME,
    )

    assert check.passed is False
    assert any("Duplicate requirement ID" in error for error in check.errors)
    assert compute_semantic_confidence(check) < 100


def test_empty_job_requirements_fails() -> None:
    gap_analysis = _valid_gap_analysis()
    gap_analysis = gap_analysis.model_copy(
        update={
            "job_requirements": [],
            "matched_resume_evidence": [],
            "revision_brief": gap_analysis.revision_brief.model_copy(
                update={
                    "must_address_requirement_ids": [],
                    "resume_evidence_to_preserve": [],
                }
            ),
        }
    )

    check = run_gap_analysis_semantic_check(
        gap_analysis=gap_analysis,
        job_description=JOB_DESCRIPTION,
        current_resume=CURRENT_RESUME,
    )

    assert check.passed is False
    assert any("no job_requirements" in error for error in check.errors)
    assert compute_semantic_confidence(check) < 100


def test_low_relevance_item_ungrounded_fails() -> None:
    gap_analysis = _valid_gap_analysis()
    gap_analysis = gap_analysis.model_copy(
        update={
            "low_relevance_items": [
                LowRelevanceItem(
                    item_id="LOW-001",
                    resume_section="Experience",
                    text="Managed a retail store for five years.",
                    reason="Not relevant to a technical role.",
                    recommendation="remove",
                )
            ]
        }
    )

    check = run_gap_analysis_semantic_check(
        gap_analysis=gap_analysis,
        job_description=JOB_DESCRIPTION,
        current_resume=CURRENT_RESUME,
    )

    assert check.passed is False
    assert any("Low-relevance item" in error for error in check.errors)


def test_keyword_not_in_job_description_warns_without_failing() -> None:
    gap_analysis = _valid_gap_analysis()
    gap_analysis = gap_analysis.model_copy(
        update={
            "revision_brief": gap_analysis.revision_brief.model_copy(
                update={"keywords_to_include_if_truthful": ["Kubernetes"]}
            )
        }
    )

    check = run_gap_analysis_semantic_check(
        gap_analysis=gap_analysis,
        job_description=JOB_DESCRIPTION,
        current_resume=CURRENT_RESUME,
    )

    assert check.passed is True
    assert check.status == "warning"
    assert check.errors == []
    assert any("Kubernetes" in warning for warning in check.warnings)
    assert compute_semantic_confidence(check) < 100


def test_gaps_to_address_not_in_top_level_gaps_warns_without_failing() -> None:
    gap_analysis = _valid_gap_analysis()
    gap_analysis = gap_analysis.model_copy(
        update={
            "revision_brief": gap_analysis.revision_brief.model_copy(
                update={
                    "gaps_to_address": [
                        GapItem(
                            gap_id="GAP-999",
                            requirement_id="REQ-001",
                            gap_type="weak",
                            severity="medium",
                            description="Weak evidence for testing frameworks.",
                            why_it_matters="Testing matters for this role.",
                            suggested_evidence_to_search_for=[],
                        )
                    ]
                }
            )
        }
    )

    check = run_gap_analysis_semantic_check(
        gap_analysis=gap_analysis,
        job_description=JOB_DESCRIPTION,
        current_resume=CURRENT_RESUME,
    )

    assert check.passed is True
    assert check.status == "warning"
    assert check.errors == []
    assert any("GAP-999" in warning for warning in check.warnings)
