from __future__ import annotations

from src.agents.gap_analyst_agent import GapAnalystAgent
from src.schemas import (
    GapAnalysisResult,
    GapItem,
    JobRequirement,
    ResumeEvidence,
    RevisionBrief,
)
from src.scoring import compute_fit_score


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


class _FakeLLMClient:
    """
    Stands in for LLMClient and returns a gap analysis whose LLM-provided
    estimated_fit_score deliberately disagrees with what the structured
    requirements/evidence/gaps actually support.
    """

    def invoke_structured(self, system_prompt, user_prompt, output_schema):
        return GapAnalysisResult(
            target_role_summary="Role summary.",
            job_requirements=[
                JobRequirement(
                    requirement_id="REQ-001",
                    description="Required skill.",
                    priority="required",
                    category="technical skill",
                    keywords=[],
                ),
            ],
            matched_resume_evidence=[],
            gaps=[
                GapItem(
                    gap_id="GAP-001",
                    requirement_id="REQ-001",
                    gap_type="missing",
                    severity="high",
                    description="Missing entirely.",
                    why_it_matters="It matters.",
                    suggested_evidence_to_search_for=[],
                ),
            ],
            low_relevance_items=[],
            revision_brief=_empty_revision_brief(),
            overall_fit_summary="Summary.",
            estimated_fit_score=95,
        )


def test_analyze_overrides_llm_score_with_computed_score() -> None:
    agent = GapAnalystAgent(llm_client=_FakeLLMClient())

    result = agent.analyze(
        job_description="A job description.",
        current_resume="A current resume.",
    )

    assert result.estimated_fit_score == 0
    # The final fit score/summary must also be threaded onto the nested
    # revision_brief, since Agent 2 only ever sees the brief, never the
    # outer GapAnalysisResult.
    assert result.revision_brief.estimated_fit_score == 0
    assert result.revision_brief.overall_fit_summary == "Summary."


class _FakeRepairLLMClient:
    """
    Stands in for LLMClient during a repair call. Records the prompts it was
    given so the test can confirm the repair path (not the initial-analysis
    path) was used, and returns a corrected, fully-supported result whose
    LLM-provided estimated_fit_score is again a freeform guess that should be
    overridden.
    """

    def __init__(self) -> None:
        self.system_prompt: str | None = None
        self.user_prompt: str | None = None

    def invoke_structured(self, system_prompt, user_prompt, output_schema):
        self.system_prompt = system_prompt
        self.user_prompt = user_prompt

        evidence = ResumeEvidence(
            evidence_id="EVID-001",
            resume_section="Projects",
            text="A current resume.",
            supported_requirement_ids=["REQ-001"],
            strength="strong",
            explanation="Directly supports the requirement.",
        )

        return GapAnalysisResult(
            target_role_summary="Role summary.",
            job_requirements=[
                JobRequirement(
                    requirement_id="REQ-001",
                    description="Required skill.",
                    priority="required",
                    category="technical skill",
                    keywords=[],
                ),
            ],
            matched_resume_evidence=[evidence],
            gaps=[],
            low_relevance_items=[],
            revision_brief=RevisionBrief(
                target_role_summary="Role summary.",
                must_address_requirement_ids=["REQ-001"],
                keywords_to_include_if_truthful=[],
                gaps_to_address=[],
                resume_evidence_to_preserve=[evidence],
                low_relevance_items_to_reduce=[],
                instructions_for_revision_agent=[],
            ),
            overall_fit_summary="Summary.",
            estimated_fit_score=99,
        )


def test_repair_sends_previous_result_and_errors_and_overrides_score() -> None:
    fake_client = _FakeRepairLLMClient()
    agent = GapAnalystAgent(llm_client=fake_client)

    previous_result = GapAnalysisResult(
        target_role_summary="Role summary.",
        job_requirements=[
            JobRequirement(
                requirement_id="REQ-001",
                description="Required skill.",
                priority="required",
                category="technical skill",
                keywords=[],
            ),
        ],
        matched_resume_evidence=[],
        gaps=[
            GapItem(
                gap_id="GAP-001",
                requirement_id="REQ-001",
                gap_type="missing",
                severity="high",
                description="Missing entirely.",
                why_it_matters="It matters.",
                suggested_evidence_to_search_for=[],
            ),
        ],
        low_relevance_items=[],
        revision_brief=_empty_revision_brief(),
        overall_fit_summary="Summary.",
        estimated_fit_score=95,
    )
    validation_errors = ["Evidence EVID-001 text was not found in current_resume."]

    result = agent.repair(
        job_description="A job description.",
        current_resume="A current resume.",
        previous_result=previous_result,
        validation_errors=validation_errors,
    )

    assert fake_client.user_prompt is not None
    assert "Evidence EVID-001 text was not found in current_resume." in fake_client.user_prompt
    assert "Role summary." in fake_client.user_prompt

    # The LLM's own freeform score (99) must still be replaced by the
    # deterministic score computed from the corrected structured result.
    assert result.estimated_fit_score != 99
    assert result.estimated_fit_score == compute_fit_score(
        result.model_copy(update={"estimated_fit_score": 99})
    )
    assert result.revision_brief.estimated_fit_score == result.estimated_fit_score
    assert result.revision_brief.overall_fit_summary == "Summary."
