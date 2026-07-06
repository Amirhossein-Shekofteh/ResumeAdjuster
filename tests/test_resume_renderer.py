from __future__ import annotations

from src.resume_renderer import render_change_summary, render_updated_resume
from src.schemas import ResumeChange, ResumeRevisionResult


def _sample_resume_revision_result() -> ResumeRevisionResult:
    return ResumeRevisionResult(
        updated_resume_markdown="# Student Name\n\n## Skills\n\n- Python\n- SQL",
        changes=[
            ResumeChange(
                change_id="CHG-001",
                change_type="add",
                resume_section="Skills",
                before=None,
                after="Added Python and SQL to Skills section.",
                reason="These skills are supported by coursework and relevant to the target role.",
                evidence_source="Coursework/student background information.",
            )
        ],
        added_keywords=["Python", "SQL"],
        removed_or_reduced_items=["Reduced unrelated club detail."],
        evidence_used_from_coursework=[
            "Completed database course using SQL.",
            "Completed Python data analysis assignment.",
        ],
        warnings=["Could not verify cloud deployment experience."],
        revision_summary="Updated the resume to emphasize relevant technical coursework.",
    )


def test_updated_resume_renders_from_revision_result() -> None:
    revision = _sample_resume_revision_result()

    rendered = render_updated_resume(revision)

    assert "# Student Name" in rendered
    assert "Python" in rendered
    assert "SQL" in rendered


def test_updated_resume_renders_from_string() -> None:
    rendered = render_updated_resume("# Resume\n\nUpdated content")

    assert rendered == "# Resume\n\nUpdated content"


def test_change_summary_renders_correctly() -> None:
    revision = _sample_resume_revision_result()

    rendered = render_change_summary(revision)

    assert "Revision Summary" in rendered
    assert "Changes Made" in rendered
    assert "CHG-001" in rendered
    assert "Keywords Added Truthfully" in rendered
    assert "`Python`" in rendered
    assert "`SQL`" in rendered
    assert "Warnings" in rendered