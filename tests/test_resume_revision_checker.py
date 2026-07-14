from __future__ import annotations

from src.checks.resume_revision_checker import (
    finalize_unsupported_resume_revision,
    run_resume_revision_semantic_check,
)
from src.schemas import ResumeChange, ResumeRevisionResult


CURRENT_RESUME = (
    "Built a Python project for analyzing student survey data. "
    "Worked as a cashier at a local grocery store for two years."
)
COURSEWORK_STUDENT_INFO = (
    "Completed a Data Structures course. Completed a Machine Learning "
    "certification through an online bootcamp."
)
UPDATED_RESUME_MARKDOWN = (
    "# Student Name\n\n"
    "## Education\n\nB.S. in Computer Science (in progress).\n\n"
    "## Projects\n\n- Built a Python project for analyzing student survey data.\n\n"
    "## Skills\n\n- Python"
)


def _valid_resume_revision() -> ResumeRevisionResult:
    return ResumeRevisionResult(
        updated_resume_markdown=UPDATED_RESUME_MARKDOWN,
        changes=[
            ResumeChange(
                change_id="CHG-001",
                change_type="rewrite",
                resume_section="Projects",
                before="Worked on class project.",
                after="Built a Python project for analyzing student survey data.",
                reason="More specific and aligned with the target role.",
                evidence_source="Built a Python project for analyzing student survey data.",
            ),
            ResumeChange(
                change_id="CHG-002",
                change_type="remove",
                resume_section="Experience",
                before="Worked as a cashier at a local grocery store for two years.",
                after=None,
                reason="Not relevant to the target role.",
                evidence_source="Original resume.",
            ),
            ResumeChange(
                change_id="CHG-003",
                change_type="keep",
                resume_section="Education",
                before="B.S. in Computer Science (in progress).",
                after="B.S. in Computer Science (in progress).",
                reason="Already strong and relevant.",
                evidence_source="Original resume.",
            ),
        ],
        added_keywords=["Python"],
        removed_or_reduced_items=["Cashier experience"],
        evidence_used_from_coursework=["Data Structures course"],
        warnings=[],
        revision_summary=(
            "Rewrote the projects section, removed irrelevant retail experience, "
            "and kept the education section as-is."
        ),
    )


def test_valid_resume_revision_passes_with_full_confidence() -> None:
    check = run_resume_revision_semantic_check(
        resume_revision=_valid_resume_revision(),
        current_resume=CURRENT_RESUME,
        coursework_student_info=COURSEWORK_STUDENT_INFO,
    )

    assert check.status == "pass"
    assert check.passed is True
    assert check.errors == []


def test_unverifiable_add_change_after_not_found_fails() -> None:
    resume_revision = _valid_resume_revision()
    resume_revision.changes.append(
        ResumeChange(
            change_id="CHG-004",
            change_type="add",
            resume_section="Education",
            before=None,
            after="Completed advanced calculus coursework with distinction.",
            reason="Adds academic strength.",
            evidence_source="Coursework records.",
        )
    )

    check = run_resume_revision_semantic_check(
        resume_revision=resume_revision,
        current_resume=CURRENT_RESUME,
        coursework_student_info=COURSEWORK_STUDENT_INFO,
    )

    assert check.passed is False
    assert any("CHG-004" in error and "unverifiable" in error for error in check.errors)


def test_empty_evidence_source_on_rewrite_fails() -> None:
    resume_revision = _valid_resume_revision()
    changes = list(resume_revision.changes)
    changes[0] = changes[0].model_copy(update={"evidence_source": "   "})
    resume_revision = resume_revision.model_copy(update={"changes": changes})

    check = run_resume_revision_semantic_check(
        resume_revision=resume_revision,
        current_resume=CURRENT_RESUME,
        coursework_student_info=COURSEWORK_STUDENT_INFO,
    )

    assert check.passed is False
    assert any("CHG-001" in error and "unverifiable" in error for error in check.errors)


def test_evidence_source_label_instead_of_quote_fails_even_if_after_is_present() -> None:
    """
    A change whose `after` text is genuinely present in the resume must still
    fail if evidence_source is a category label (e.g. "coursework info")
    rather than a real quote from the source documents -- this is the hole
    that let fabricated-but-plausible-sounding bullets pass validation.
    """

    resume_revision = _valid_resume_revision()
    changes = list(resume_revision.changes)
    changes.append(
        ResumeChange(
            change_id="CHG-005",
            change_type="add",
            resume_section="Skills",
            before=None,
            after="Python",
            reason="Highlights a relevant technical skill.",
            evidence_source="Relevant technical background.",
        )
    )
    resume_revision = resume_revision.model_copy(update={"changes": changes})

    check = run_resume_revision_semantic_check(
        resume_revision=resume_revision,
        current_resume=CURRENT_RESUME,
        coursework_student_info=COURSEWORK_STUDENT_INFO,
    )

    assert check.passed is False
    assert any("CHG-005" in error and "unverifiable" in error for error in check.errors)


def test_evidence_source_grounded_in_coursework_passes() -> None:
    resume_revision = _valid_resume_revision()
    changes = list(resume_revision.changes)
    changes.append(
        ResumeChange(
            change_id="CHG-005",
            change_type="add",
            resume_section="Skills",
            before=None,
            after="Completed a Data Structures course.",
            reason="Adds relevant coursework.",
            evidence_source="Completed a Data Structures course.",
        )
    )
    resume_revision = resume_revision.model_copy(
        update={
            "changes": changes,
            "updated_resume_markdown": UPDATED_RESUME_MARKDOWN
            + "\n- Completed a Data Structures course.",
        }
    )

    check = run_resume_revision_semantic_check(
        resume_revision=resume_revision,
        current_resume=CURRENT_RESUME,
        coursework_student_info=COURSEWORK_STUDENT_INFO,
    )

    assert check.passed is True
    assert check.errors == []


def test_incomplete_removal_fails() -> None:
    resume_revision = _valid_resume_revision()
    markdown_with_leftover = (
        UPDATED_RESUME_MARKDOWN
        + "\n\n## Experience\n\nWorked as a cashier at a local grocery store for two years."
    )
    resume_revision = resume_revision.model_copy(
        update={"updated_resume_markdown": markdown_with_leftover}
    )

    check = run_resume_revision_semantic_check(
        resume_revision=resume_revision,
        current_resume=CURRENT_RESUME,
        coursework_student_info=COURSEWORK_STUDENT_INFO,
    )

    assert check.passed is False
    assert any("CHG-002" in error and "claims removal" in error for error in check.errors)


def test_duplicate_change_id_fails() -> None:
    resume_revision = _valid_resume_revision()
    changes = list(resume_revision.changes)
    changes.append(changes[0])
    resume_revision = resume_revision.model_copy(update={"changes": changes})

    check = run_resume_revision_semantic_check(
        resume_revision=resume_revision,
        current_resume=CURRENT_RESUME,
        coursework_student_info=COURSEWORK_STUDENT_INFO,
    )

    assert check.passed is False
    assert any("Duplicate change ID" in error for error in check.errors)


def test_keyword_missing_from_markdown_fails() -> None:
    resume_revision = _valid_resume_revision()
    resume_revision = resume_revision.model_copy(
        update={"added_keywords": ["Django"]}
    )

    check = run_resume_revision_semantic_check(
        resume_revision=resume_revision,
        current_resume=CURRENT_RESUME,
        coursework_student_info=COURSEWORK_STUDENT_INFO,
    )

    assert check.passed is False
    assert any(
        "Django" in error and "does not appear" in error for error in check.errors
    )


def test_keyword_present_but_unsupported_fails_as_hard_error() -> None:
    resume_revision = _valid_resume_revision()
    markdown_with_keyword = UPDATED_RESUME_MARKDOWN + "\n- Kubernetes"
    resume_revision = resume_revision.model_copy(
        update={
            "updated_resume_markdown": markdown_with_keyword,
            "added_keywords": ["Python", "Kubernetes"],
        }
    )

    check = run_resume_revision_semantic_check(
        resume_revision=resume_revision,
        current_resume=CURRENT_RESUME,
        coursework_student_info=COURSEWORK_STUDENT_INFO,
    )

    # Truthfulness must be a hard error, not a soft warning.
    assert check.passed is False
    assert check.status == "fail"
    assert any(
        "Kubernetes" in error and "not supported" in error for error in check.errors
    )


def test_coursework_evidence_not_grounded_fails_as_hard_error() -> None:
    resume_revision = _valid_resume_revision()
    resume_revision = resume_revision.model_copy(
        update={"evidence_used_from_coursework": ["Robotics club leadership"]}
    )

    check = run_resume_revision_semantic_check(
        resume_revision=resume_revision,
        current_resume=CURRENT_RESUME,
        coursework_student_info=COURSEWORK_STUDENT_INFO,
    )

    assert check.passed is False
    assert check.status == "fail"
    assert any("Robotics club leadership" in error for error in check.errors)


def test_empty_markdown_fails() -> None:
    resume_revision = ResumeRevisionResult(
        updated_resume_markdown="   ",
        changes=[],
        added_keywords=[],
        removed_or_reduced_items=[],
        evidence_used_from_coursework=[],
        warnings=[],
        revision_summary="Summary.",
    )

    check = run_resume_revision_semantic_check(
        resume_revision=resume_revision,
        current_resume=CURRENT_RESUME,
        coursework_student_info=COURSEWORK_STUDENT_INFO,
    )

    assert check.passed is False
    assert any("updated_resume_markdown is empty" in error for error in check.errors)


def test_finalize_strips_unsupported_keyword() -> None:
    markdown_with_keyword = UPDATED_RESUME_MARKDOWN + "\n- Kubernetes"
    resume_revision = _valid_resume_revision().model_copy(
        update={
            "updated_resume_markdown": markdown_with_keyword,
            "added_keywords": ["Python", "Kubernetes"],
        }
    )

    finalized = finalize_unsupported_resume_revision(
        resume_revision=resume_revision,
        current_resume=CURRENT_RESUME,
        coursework_student_info=COURSEWORK_STUDENT_INFO,
    )

    assert "kubernetes" not in finalized.updated_resume_markdown.lower()
    assert "Kubernetes" not in finalized.added_keywords
    assert "Python" in finalized.added_keywords
    assert any(
        change.change_type == "remove"
        and "not supported" in change.reason
        and change.before == "Kubernetes"
        for change in finalized.changes
    )
    assert finalized.semantic_confidence == 100
    assert finalized.semantic_warnings != []


def test_finalize_strips_incomplete_removal() -> None:
    markdown_with_leftover = (
        UPDATED_RESUME_MARKDOWN
        + "\n\n## Experience\n\nWorked as a cashier at a local grocery store for two years."
    )
    resume_revision = _valid_resume_revision().model_copy(
        update={"updated_resume_markdown": markdown_with_leftover}
    )

    finalized = finalize_unsupported_resume_revision(
        resume_revision=resume_revision,
        current_resume=CURRENT_RESUME,
        coursework_student_info=COURSEWORK_STUDENT_INFO,
    )

    assert "cashier" not in finalized.updated_resume_markdown.lower()
    assert finalized.semantic_confidence == 100


def test_finalize_converts_unverifiable_change_to_remove() -> None:
    resume_revision = _valid_resume_revision()
    changes = list(resume_revision.changes)
    changes.append(
        ResumeChange(
            change_id="CHG-004",
            change_type="add",
            resume_section="Education",
            before=None,
            after="Completed advanced calculus coursework with distinction.",
            reason="Adds academic strength.",
            evidence_source="Coursework records.",
        )
    )
    resume_revision = resume_revision.model_copy(update={"changes": changes})

    finalized = finalize_unsupported_resume_revision(
        resume_revision=resume_revision,
        current_resume=CURRENT_RESUME,
        coursework_student_info=COURSEWORK_STUDENT_INFO,
    )

    finalized_chg_004 = next(
        change for change in finalized.changes if change.change_id == "CHG-004"
    )
    assert finalized_chg_004.change_type == "remove"
    assert "could not be verified" in finalized_chg_004.reason
    assert finalized.semantic_confidence == 100


def test_finalize_drops_unsupported_coursework_evidence_with_warning() -> None:
    resume_revision = _valid_resume_revision().model_copy(
        update={"evidence_used_from_coursework": ["Robotics club leadership"]}
    )

    finalized = finalize_unsupported_resume_revision(
        resume_revision=resume_revision,
        current_resume=CURRENT_RESUME,
        coursework_student_info=COURSEWORK_STUDENT_INFO,
    )

    assert "Robotics club leadership" not in finalized.evidence_used_from_coursework
    assert any(
        "Robotics club leadership" in warning for warning in finalized.semantic_warnings
    )
    # Can't auto-locate/strip specific markdown text for this one -- flagged, not silently passed.
    assert finalized.semantic_confidence == 100


def test_keep_already_strong_unchanged_passes() -> None:
    resume_revision = ResumeRevisionResult(
        decision="keep_already_strong",
        updated_resume_markdown=CURRENT_RESUME,
        changes=[],
        added_keywords=[],
        removed_or_reduced_items=[],
        evidence_used_from_coursework=[],
        warnings=[],
        revision_summary="The resume already fits this role well.",
    )

    check = run_resume_revision_semantic_check(
        resume_revision=resume_revision,
        current_resume=CURRENT_RESUME,
        coursework_student_info=COURSEWORK_STUDENT_INFO,
    )

    assert check.passed is True
    assert check.errors == []


def test_keep_decision_with_reported_changes_fails() -> None:
    resume_revision = _valid_resume_revision().model_copy(
        update={"decision": "keep_already_strong"}
    )

    check = run_resume_revision_semantic_check(
        resume_revision=resume_revision,
        current_resume=CURRENT_RESUME,
        coursework_student_info=COURSEWORK_STUDENT_INFO,
    )

    assert check.passed is False
    assert any(
        "keep_already_strong" in error and "changes were reported" in error
        for error in check.errors
    )


def test_keep_decision_with_modified_markdown_fails() -> None:
    resume_revision = ResumeRevisionResult(
        decision="keep_insufficient_fit",
        updated_resume_markdown=CURRENT_RESUME + "\n\nExtra unauthorized line.",
        changes=[],
        added_keywords=[],
        removed_or_reduced_items=[],
        evidence_used_from_coursework=[],
        warnings=[],
        revision_summary="Not enough evidence for this role.",
    )

    check = run_resume_revision_semantic_check(
        resume_revision=resume_revision,
        current_resume=CURRENT_RESUME,
        coursework_student_info=COURSEWORK_STUDENT_INFO,
    )

    assert check.passed is False
    assert any(
        "keep_insufficient_fit" in error and "differs" in error
        for error in check.errors
    )


def test_revise_decision_with_no_actual_change_fails() -> None:
    resume_revision = ResumeRevisionResult(
        decision="revise",
        updated_resume_markdown=CURRENT_RESUME,
        changes=[],
        added_keywords=[],
        removed_or_reduced_items=[],
        evidence_used_from_coursework=[],
        warnings=[],
        revision_summary="Rewrote the whole resume.",
    )

    check = run_resume_revision_semantic_check(
        resume_revision=resume_revision,
        current_resume=CURRENT_RESUME,
        coursework_student_info=COURSEWORK_STUDENT_INFO,
    )

    assert check.passed is False
    assert any(
        "'revise' but updated_resume_markdown is identical" in error
        for error in check.errors
    )


def test_finalize_reverts_keep_decision_that_actually_changed_content() -> None:
    resume_revision = _valid_resume_revision().model_copy(
        update={"decision": "keep_already_strong"}
    )

    finalized = finalize_unsupported_resume_revision(
        resume_revision=resume_revision,
        current_resume=CURRENT_RESUME,
        coursework_student_info=COURSEWORK_STUDENT_INFO,
    )

    assert finalized.decision == "keep_already_strong"
    assert finalized.updated_resume_markdown == CURRENT_RESUME
    assert finalized.changes == []
    assert finalized.added_keywords == []
    assert finalized.removed_or_reduced_items == []
    assert any("Decision was" in warning for warning in finalized.semantic_warnings)


def test_finalize_flips_no_op_revise_to_keep_already_strong() -> None:
    resume_revision = ResumeRevisionResult(
        decision="revise",
        updated_resume_markdown=CURRENT_RESUME,
        changes=[],
        added_keywords=[],
        removed_or_reduced_items=[],
        evidence_used_from_coursework=[],
        warnings=[],
        revision_summary="Rewrote the whole resume.",
    )

    finalized = finalize_unsupported_resume_revision(
        resume_revision=resume_revision,
        current_resume=CURRENT_RESUME,
        coursework_student_info=COURSEWORK_STUDENT_INFO,
    )

    assert finalized.decision == "keep_already_strong"
    assert any(
        "changed decision to 'keep_already_strong'" in warning
        for warning in finalized.semantic_warnings
    )


def test_finalize_relabels_revise_as_insufficient_fit_when_evidence_fails() -> None:
    """
    When every proposed change fails truthfulness verification (fabricated
    evidence_source), finalize must not silently ship the stripped-down
    resume as a "revise", nor mislabel it "keep_already_strong" (which would
    imply the resume was already fine) -- it should say plainly that there
    wasn't enough truthful evidence to strengthen it.
    """

    fabricated_claim = (
        "Extensive Python expertise architecting large-scale production systems."
    )
    resume_revision = ResumeRevisionResult(
        decision="revise",
        updated_resume_markdown=CURRENT_RESUME + " " + fabricated_claim,
        changes=[
            ResumeChange(
                change_id="CHG-001",
                change_type="add",
                resume_section="Skills",
                before=None,
                after=fabricated_claim,
                reason="Highlights strong Python skills.",
                evidence_source="Demonstrated strong technical ability.",
            )
        ],
        added_keywords=[],
        removed_or_reduced_items=[],
        evidence_used_from_coursework=[],
        warnings=[],
        revision_summary="Added emphasis on Python expertise.",
    )

    finalized = finalize_unsupported_resume_revision(
        resume_revision=resume_revision,
        current_resume=CURRENT_RESUME,
        coursework_student_info=COURSEWORK_STUDENT_INFO,
    )

    assert finalized.decision == "keep_insufficient_fit"
    assert fabricated_claim not in finalized.updated_resume_markdown
    assert finalized.revision_summary.startswith("Automated note:")
    assert any(
        "keep_insufficient_fit" in warning and "verification" in warning
        for warning in finalized.semantic_warnings
    )


def test_finalize_deduplicates_change_ids() -> None:
    resume_revision = _valid_resume_revision()
    changes = list(resume_revision.changes)
    changes.append(changes[0])
    resume_revision = resume_revision.model_copy(update={"changes": changes})

    finalized = finalize_unsupported_resume_revision(
        resume_revision=resume_revision,
        current_resume=CURRENT_RESUME,
        coursework_student_info=COURSEWORK_STUDENT_INFO,
    )

    change_ids = [change.change_id for change in finalized.changes]
    assert len(change_ids) == len(set(change_ids))
    assert finalized.semantic_confidence == 100
