from __future__ import annotations

from src.agents.resume_revision_agent import ResumeRevisionAgent
from src.schemas import ResumeChange, ResumeRevisionResult, RevisionBrief


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


class _FakeRepairLLMClient:
    """
    Stands in for LLMClient during a repair call. Records the prompts it was
    given so the test can confirm the repair path (not the initial-revision
    path) was used.
    """

    def __init__(self) -> None:
        self.system_prompt: str | None = None
        self.user_prompt: str | None = None

    def invoke_structured(self, system_prompt, user_prompt, output_schema):
        self.system_prompt = system_prompt
        self.user_prompt = user_prompt

        return ResumeRevisionResult(
            updated_resume_markdown="# Student Name\n\n## Skills\n\n- Python",
            changes=[
                ResumeChange(
                    change_id="CHG-001",
                    change_type="rewrite",
                    resume_section="Skills",
                    before="Worked on projects.",
                    after="Built a Python project.",
                    reason="Corrected per validation errors.",
                    evidence_source="Original resume.",
                )
            ],
            added_keywords=["Python"],
            removed_or_reduced_items=[],
            evidence_used_from_coursework=[],
            warnings=[],
            revision_summary="Corrected the resume revision after validation errors.",
        )


def test_repair_sends_previous_result_and_errors() -> None:
    fake_client = _FakeRepairLLMClient()
    agent = ResumeRevisionAgent(llm_client=fake_client)

    previous_result = ResumeRevisionResult(
        updated_resume_markdown="# Student Name\n\n## Skills\n\n- Kubernetes",
        changes=[],
        added_keywords=["Kubernetes"],
        removed_or_reduced_items=[],
        evidence_used_from_coursework=[],
        warnings=[],
        revision_summary="Added Kubernetes as a skill.",
    )
    validation_errors = [
        "Added keyword 'Kubernetes' is not supported by the current resume or "
        "coursework/student background information."
    ]

    result = agent.repair(
        current_resume="A current resume.",
        coursework_student_info="Some coursework information.",
        revision_brief=_empty_revision_brief(),
        previous_result=previous_result,
        validation_errors=validation_errors,
    )

    assert fake_client.user_prompt is not None
    assert (
        "Added keyword 'Kubernetes' is not supported by the current resume or "
        "coursework/student background information." in fake_client.user_prompt
    )
    assert "Added Kubernetes as a skill." in fake_client.user_prompt
    assert result.updated_resume_markdown == "# Student Name\n\n## Skills\n\n- Python"
    assert result.added_keywords == ["Python"]


class _FakeReviseLLMClient:
    """
    Stands in for LLMClient during an initial (non-repair) revise() call.
    """

    def __init__(self, result: ResumeRevisionResult) -> None:
        self._result = result

    def invoke_structured(self, system_prompt, user_prompt, output_schema):
        return self._result


def test_revise_decision_passes_through_untouched() -> None:
    fake_result = ResumeRevisionResult(
        decision="revise",
        updated_resume_markdown="# Student Name\n\n## Skills\n\n- Python",
        changes=[
            ResumeChange(
                change_id="CHG-001",
                change_type="add",
                resume_section="Skills",
                before=None,
                after="Python",
                reason="Added a truthfully supported skill.",
                evidence_source="Original resume.",
            )
        ],
        added_keywords=["Python"],
        removed_or_reduced_items=[],
        evidence_used_from_coursework=[],
        warnings=[],
        revision_summary="Added Python as a skill.",
    )
    agent = ResumeRevisionAgent(llm_client=_FakeReviseLLMClient(fake_result))

    result = agent.revise(
        current_resume="A current resume.",
        coursework_student_info="Some coursework information.",
        revision_brief=_empty_revision_brief(),
    )

    assert result.decision == "revise"
    assert result.updated_resume_markdown == "# Student Name\n\n## Skills\n\n- Python"
    assert len(result.changes) == 1
    assert result.added_keywords == ["Python"]


def test_keep_decision_is_normalized_to_the_original_resume_in_revise() -> None:
    fake_result = ResumeRevisionResult(
        decision="keep_already_strong",
        # The LLM claims to have kept the resume unchanged, but it actually
        # reformatted content and reported changes -- the normalization step
        # must override this rather than trust the LLM's copy fidelity.
        updated_resume_markdown="# Student Name (reformatted)\n\n## Skills\n\n- Python",
        changes=[
            ResumeChange(
                change_id="CHG-001",
                change_type="rewrite",
                resume_section="Skills",
                before="Python",
                after="Python",
                reason="Tidied formatting.",
                evidence_source="Original resume.",
            )
        ],
        added_keywords=["Python"],
        removed_or_reduced_items=["Old bullet"],
        evidence_used_from_coursework=[],
        warnings=[],
        revision_summary="The resume already fits this role well.",
    )
    agent = ResumeRevisionAgent(llm_client=_FakeReviseLLMClient(fake_result))
    current_resume = "A current resume."

    result = agent.revise(
        current_resume=current_resume,
        coursework_student_info="Some coursework information.",
        revision_brief=_empty_revision_brief(),
    )

    assert result.decision == "keep_already_strong"
    assert result.updated_resume_markdown == current_resume
    assert result.changes == []
    assert result.added_keywords == []
    assert result.removed_or_reduced_items == []
    # The explanation is preserved -- only the content-tracking fields are reset.
    assert result.revision_summary == "The resume already fits this role well."


def test_keep_decision_is_normalized_to_the_original_resume_in_repair() -> None:
    class _FakeKeepRepairLLMClient:
        def invoke_structured(self, system_prompt, user_prompt, output_schema):
            return ResumeRevisionResult(
                decision="keep_insufficient_fit",
                updated_resume_markdown="A current resume, but slightly reworded.",
                changes=[
                    ResumeChange(
                        change_id="CHG-001",
                        change_type="rewrite",
                        resume_section="Skills",
                        before="X",
                        after="Y",
                        reason="Should not have made this change.",
                        evidence_source="Original resume.",
                    )
                ],
                added_keywords=["X"],
                removed_or_reduced_items=[],
                evidence_used_from_coursework=[],
                warnings=[],
                revision_summary="Not enough truthful evidence for this role.",
            )

    agent = ResumeRevisionAgent(llm_client=_FakeKeepRepairLLMClient())
    current_resume = "A current resume."
    previous_result = ResumeRevisionResult(
        decision="keep_insufficient_fit",
        updated_resume_markdown="Some earlier bad output.",
        changes=[],
        added_keywords=[],
        removed_or_reduced_items=[],
        evidence_used_from_coursework=[],
        warnings=[],
        revision_summary="Previous attempt.",
    )

    result = agent.repair(
        current_resume=current_resume,
        coursework_student_info="Some coursework information.",
        revision_brief=_empty_revision_brief(),
        previous_result=previous_result,
        validation_errors=["Decision is 'keep_insufficient_fit' but changes were reported."],
    )

    assert result.decision == "keep_insufficient_fit"
    assert result.updated_resume_markdown == current_resume
    assert result.changes == []
    assert result.added_keywords == []
    assert result.removed_or_reduced_items == []
