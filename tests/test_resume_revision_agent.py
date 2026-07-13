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
