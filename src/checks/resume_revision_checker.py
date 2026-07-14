from __future__ import annotations

import re

from src.checks.semantic_check_result import (
    SemanticCheckResult,
    SemanticStatus,
    compute_semantic_confidence,
)
from src.schemas import ResumeChange, ResumeRevisionResult


def _normalize(text: str | None) -> str:
    """
    Normalize text for stable matching across PDF/DOCX whitespace artifacts.
    """

    return re.sub(r"\s+", " ", text or "").strip().lower()


def _is_present(quote: str, source_text: str) -> bool:
    """
    Return True only when the (normalized) quote appears in the source text.
    """

    normalized_quote = _normalize(quote)

    if not normalized_quote:
        return False

    return normalized_quote in _normalize(source_text)


def _flexible_pattern(quote: str) -> re.Pattern[str]:
    """
    Build a whitespace-tolerant, case-insensitive regex that locates an exact
    quote inside markdown text regardless of formatting differences, so it
    can be located and stripped in the original text.

    Word boundaries are only applied on a side whose edge token actually ends
    in a word character -- a quote ending in punctuation (e.g. a full
    sentence) already can't partially overlap an adjacent word, and `\\b`
    right after punctuation would fail to match at all.
    """

    tokens = quote.strip().split()
    body = r"\s+".join(re.escape(token) for token in tokens)

    prefix = r"\b" if tokens and tokens[0][:1].isalnum() else ""
    suffix = r"\b" if tokens and tokens[-1][-1:].isalnum() else ""

    return re.compile(rf"{prefix}{body}{suffix}", re.IGNORECASE)


def _strip_text(quote: str, markdown: str) -> str:
    """
    Remove all occurrences of `quote` from `markdown` and tidy up the
    whitespace/punctuation left behind. This is a best-effort safety-net
    edit (not a rewrite), used only when repeated repair attempts have
    failed, so the result may read a little rough around the removed spot.
    """

    if not quote.strip():
        return markdown

    stripped = _flexible_pattern(quote).sub("", markdown)
    stripped = re.sub(r"[ \t]{2,}", " ", stripped)
    stripped = re.sub(r",\s*,", ",", stripped)
    stripped = re.sub(r",[ \t]*\n", "\n", stripped)
    stripped = re.sub(r"^[ \t]*,[ \t]*", "", stripped, flags=re.MULTILINE)
    stripped = re.sub(r"^[ \t]*[-*][ \t]*$", "", stripped, flags=re.MULTILINE)
    return stripped


def _is_add_or_rewrite(change: ResumeChange) -> bool:
    return change.change_type in {"add", "rewrite"}


def _find_duplicate_change_ids(changes: list[ResumeChange]) -> set[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()

    for change in changes:
        if change.change_id in seen:
            duplicates.add(change.change_id)
        seen.add(change.change_id)

    return duplicates


def _find_unverifiable_changes(
    changes: list[ResumeChange],
    updated_resume_markdown: str,
    current_resume: str,
    coursework_student_info: str,
) -> list[ResumeChange]:
    """
    add/rewrite changes with an empty or ungrounded evidence_source, or whose
    `after` text can't be found in the final resume -- Agent 2's own report
    doesn't match reality, so the claim can't be verified.

    evidence_source must be an exact quote actually present in the current
    resume or the coursework/student background information, not just a
    non-empty category label -- a label like "coursework info" would let a
    fabricated bullet pass every other check.
    """

    unverifiable: list[ResumeChange] = []

    for change in changes:
        if not _is_add_or_rewrite(change):
            continue

        evidence_source = change.evidence_source.strip()
        evidence_ungrounded = not evidence_source or not (
            _is_present(evidence_source, current_resume)
            or _is_present(evidence_source, coursework_student_info)
        )
        after_not_found = change.after is not None and not _is_present(
            change.after, updated_resume_markdown
        )

        if evidence_ungrounded or after_not_found:
            unverifiable.append(change)

    return unverifiable


def _find_incomplete_removals(
    changes: list[ResumeChange],
    updated_resume_markdown: str,
) -> list[ResumeChange]:
    """
    "remove" changes whose `before` text still appears in the final resume.
    """

    return [
        change
        for change in changes
        if change.change_type == "remove"
        and change.before is not None
        and _is_present(change.before, updated_resume_markdown)
    ]


def _find_unlisted_keywords(
    added_keywords: list[str],
    updated_resume_markdown: str,
) -> list[str]:
    """
    Keywords Agent 2 claims to have added, but that don't actually appear in
    the final resume.
    """

    return [
        keyword
        for keyword in added_keywords
        if not _is_present(keyword, updated_resume_markdown)
    ]


def _find_unsupported_keywords(
    added_keywords: list[str],
    updated_resume_markdown: str,
    current_resume: str,
    coursework_student_info: str,
) -> list[str]:
    """
    Keywords that ARE present in the final resume, but aren't grounded in the
    current resume or the coursework/student background information --
    i.e. a fabricated skill claim that actually made it into the document.
    """

    unsupported: list[str] = []

    for keyword in added_keywords:
        if not _is_present(keyword, updated_resume_markdown):
            continue  # covered by _find_unlisted_keywords instead

        grounded = _is_present(keyword, current_resume) or _is_present(
            keyword, coursework_student_info
        )

        if not grounded:
            unsupported.append(keyword)

    return unsupported


def _find_unsupported_coursework_evidence(
    evidence_used_from_coursework: list[str],
    coursework_student_info: str,
) -> list[str]:
    return [
        item
        for item in evidence_used_from_coursework
        if not _is_present(item, coursework_student_info)
    ]


def _find_decision_consistency_issues(
    resume_revision: ResumeRevisionResult,
    current_resume: str,
) -> list[str]:
    """
    Verify that `decision` actually matches what Agent 2 produced. A "keep"
    decision that silently changed the resume, or a "revise" decision that
    changed nothing, would mislead the student about what actually happened.
    """

    issues: list[str] = []
    unchanged = _normalize(resume_revision.updated_resume_markdown) == _normalize(
        current_resume
    )

    if resume_revision.decision != "revise":
        if resume_revision.changes:
            issues.append(
                f"Decision is {resume_revision.decision!r} but changes were reported."
            )
        if resume_revision.added_keywords:
            issues.append(
                f"Decision is {resume_revision.decision!r} but added_keywords is "
                "non-empty."
            )
        if resume_revision.removed_or_reduced_items:
            issues.append(
                f"Decision is {resume_revision.decision!r} but "
                "removed_or_reduced_items is non-empty."
            )
        if not unchanged:
            issues.append(
                f"Decision is {resume_revision.decision!r} but updated_resume_markdown "
                "differs from the original current resume."
            )
    elif not resume_revision.changes and unchanged:
        issues.append(
            "Decision is 'revise' but updated_resume_markdown is identical to the "
            "original current resume and no changes were reported."
        )

    return issues


def run_resume_revision_semantic_check(
    *,
    resume_revision: ResumeRevisionResult,
    current_resume: str,
    coursework_student_info: str,
) -> SemanticCheckResult:
    """
    Validate that Agent 2's resume revision is internally consistent and
    truthfully grounded.

    Unlike Agent 1's evidence (which quotes existing resume text verbatim),
    Agent 2's `after` text is a rewrite/paraphrase, so exact-quote grounding
    against source text isn't meaningful for it. Self-consistency between the
    reported changes/keywords and the actual updated_resume_markdown, and
    truthfulness of added keywords / coursework evidence against source text,
    are both treated as hard errors: a fabricated credential on a resume is a
    real harm, not a style nit.

    Rules:
    1. updated_resume_markdown and revision_summary must not be empty.
    2. change_id must be unique.
    3. Every add/rewrite change must have an evidence_source that is a
       verbatim quote found in the current resume or the coursework/student
       background information, and its `after` text must actually appear in
       updated_resume_markdown.
    4. Every remove change's `before` text must no longer appear in
       updated_resume_markdown.
    5. Every added_keywords entry must appear in updated_resume_markdown,
       and must be grounded in the current resume or coursework/student
       background information.
    6. Every evidence_used_from_coursework entry must be grounded in the
       coursework/student background information.
    7. `decision` must be consistent with the rest of the output: a "keep_*"
       decision must leave the resume and change-tracking fields untouched,
       and a "revise" decision must not be a no-op.
    """

    errors: list[str] = []
    warnings: list[str] = []
    total_checks = 0
    failed_checks = 0

    markdown = resume_revision.updated_resume_markdown

    # 1. Non-empty output.
    for field_name, value in (
        ("updated_resume_markdown", resume_revision.updated_resume_markdown),
        ("revision_summary", resume_revision.revision_summary),
    ):
        total_checks += 1
        if not value.strip():
            failed_checks += 1
            errors.append(f"Agent 2's {field_name} is empty.")

    # 2. change_id uniqueness.
    total_checks += 1
    duplicates = _find_duplicate_change_ids(resume_revision.changes)
    if duplicates:
        failed_checks += 1
        errors.append(
            f"Duplicate change ID(s) found: {', '.join(sorted(duplicates))}."
        )

    # 3. add/rewrite changes must be verifiable.
    add_rewrite_changes = [
        change for change in resume_revision.changes if _is_add_or_rewrite(change)
    ]
    unverifiable_changes = _find_unverifiable_changes(
        resume_revision.changes, markdown, current_resume, coursework_student_info
    )
    total_checks += len(add_rewrite_changes)
    failed_checks += len(unverifiable_changes)
    for change in unverifiable_changes:
        errors.append(
            f"Change {change.change_id} is unverifiable: its evidence_source "
            f"({change.evidence_source!r}) is not a verbatim quote found in the "
            "current resume or coursework/student background information, or its "
            f"`after` text was not found in updated_resume_markdown ({change.after!r})."
        )

    # 4. remove changes must actually be gone.
    remove_changes = [
        change
        for change in resume_revision.changes
        if change.change_type == "remove" and change.before is not None
    ]
    incomplete_removals = _find_incomplete_removals(resume_revision.changes, markdown)
    total_checks += len(remove_changes)
    failed_checks += len(incomplete_removals)
    for change in incomplete_removals:
        errors.append(
            f"Change {change.change_id} claims removal, but its `before` text still "
            f"appears in updated_resume_markdown: {change.before!r}."
        )

    # 5. added_keywords must be present in the resume and grounded in a real source.
    for keyword in resume_revision.added_keywords:
        total_checks += 1
        in_markdown = _is_present(keyword, markdown)

        if not in_markdown:
            failed_checks += 1
            errors.append(
                f"Added keyword {keyword!r} does not appear in updated_resume_markdown."
            )
            continue

        grounded = _is_present(keyword, current_resume) or _is_present(
            keyword, coursework_student_info
        )

        if not grounded:
            failed_checks += 1
            errors.append(
                f"Added keyword {keyword!r} is not supported by the current resume "
                "or coursework/student background information."
            )

    # 6. evidence_used_from_coursework must be grounded in the coursework text.
    unsupported_evidence = _find_unsupported_coursework_evidence(
        resume_revision.evidence_used_from_coursework, coursework_student_info
    )
    total_checks += len(resume_revision.evidence_used_from_coursework)
    failed_checks += len(unsupported_evidence)
    for item in unsupported_evidence:
        errors.append(
            f"evidence_used_from_coursework item {item!r} was not found in the "
            "coursework/student background information."
        )

    # 7. decision must be consistent with the rest of the output.
    decision_issues = _find_decision_consistency_issues(resume_revision, current_resume)
    total_checks += 1
    if decision_issues:
        failed_checks += 1
        errors.extend(decision_issues)

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


def finalize_unsupported_resume_revision(
    *,
    resume_revision: ResumeRevisionResult,
    current_resume: str,
    coursework_student_info: str,
) -> ResumeRevisionResult:
    """
    Deterministically strip content that still fails semantic validation after
    repair attempts are exhausted. No LLM call.

    Never silently drops content: every mechanical edit is recorded as a
    visible ResumeChange (or a semantic_warnings note), so a human reviewing
    the resume can see exactly what was auto-removed and why.
    """

    markdown = resume_revision.updated_resume_markdown
    changes = list(resume_revision.changes)
    added_keywords = list(resume_revision.added_keywords)
    evidence_used_from_coursework = list(resume_revision.evidence_used_from_coursework)
    finalize_notes: list[str] = []

    # De-duplicate change_id (keep first occurrence).
    duplicates = _find_duplicate_change_ids(changes)
    if duplicates:
        seen: set[str] = set()
        deduped: list[ResumeChange] = []
        for change in changes:
            if change.change_id in duplicates and change.change_id in seen:
                continue
            seen.add(change.change_id)
            deduped.append(change)
        changes = deduped
        finalize_notes.append(
            f"Removed {len(duplicates)} duplicate change ID(s): "
            f"{', '.join(sorted(duplicates))}."
        )

    # Keywords: strip + drop unsupported ones, drop unlisted ones. Done before
    # the change-level checks below, since stripping a keyword out of the
    # markdown can itself invalidate a change record that depended on it.
    unlisted_keywords = _find_unlisted_keywords(added_keywords, markdown)
    unsupported_keywords = _find_unsupported_keywords(
        added_keywords, markdown, current_resume, coursework_student_info
    )

    for index, keyword in enumerate(unsupported_keywords, start=1):
        markdown = _strip_text(keyword, markdown)
        changes.append(
            ResumeChange(
                change_id=f"AUTO-REMOVE-KEYWORD-{index}",
                change_type="remove",
                resume_section="(automated validation)",
                before=keyword,
                after=None,
                reason=(
                    "Automatically removed: not supported by the resume or "
                    "coursework/student background information."
                ),
                evidence_source="Deterministic semantic validation.",
            )
        )
        finalize_notes.append(f"Automatically removed unsupported keyword {keyword!r}.")

    for keyword in unlisted_keywords:
        finalize_notes.append(
            f"Dropped claimed keyword {keyword!r}: it was never actually present in "
            "updated_resume_markdown."
        )

    dropped_keywords = set(unsupported_keywords) | set(unlisted_keywords)
    added_keywords = [
        keyword for keyword in added_keywords if keyword not in dropped_keywords
    ]

    # Incomplete removals: strip the lingering `before` text.
    for change in _find_incomplete_removals(changes, markdown):
        if change.before:
            markdown = _strip_text(change.before, markdown)
        finalize_notes.append(
            f"Enforced removal for change {change.change_id}: its text still "
            "appeared after Agent 2 claimed it was removed."
        )

    # Unverifiable add/rewrite changes: strip if present, convert to a visible
    # removal. Recomputed against the markdown as modified above, so a change
    # that only became unverifiable because its keyword was just stripped is
    # still caught and reconciled here.
    unverifiable_ids = {
        change.change_id
        for change in _find_unverifiable_changes(
            changes, markdown, current_resume, coursework_student_info
        )
    }
    updated_changes: list[ResumeChange] = []
    for change in changes:
        if change.change_id in unverifiable_ids:
            if change.after:
                markdown = _strip_text(change.after, markdown)
            change = change.model_copy(
                update={
                    "change_type": "remove",
                    "reason": (
                        "Automatically removed: could not be verified. "
                        + change.reason
                    ),
                }
            )
            finalize_notes.append(
                f"Automatically removed unverifiable change {change.change_id}."
            )
        updated_changes.append(change)
    changes = updated_changes

    # Coursework evidence: drop unsupported entries, note for manual review.
    unsupported_evidence = _find_unsupported_coursework_evidence(
        evidence_used_from_coursework, coursework_student_info
    )
    if unsupported_evidence:
        evidence_used_from_coursework = [
            item
            for item in evidence_used_from_coursework
            if item not in unsupported_evidence
        ]
        finalize_notes.append(
            "Could not verify the following coursework evidence claims; removed from "
            "evidence_used_from_coursework and flagged for manual review: "
            + "; ".join(unsupported_evidence)
        )

    # Decision consistency: resolve any remaining mismatch between `decision`
    # and what was actually produced, deterministically and in the direction
    # that can never fabricate content -- a "keep" decision wins over any
    # reported changes, and a no-op "revise" is relabeled as "kept as-is".
    decision = resume_revision.decision
    removed_or_reduced_items = list(resume_revision.removed_or_reduced_items)
    markdown_unchanged = _normalize(markdown) == _normalize(current_resume)
    revision_summary = resume_revision.revision_summary

    # Was anything actually stripped above for failing truthfulness
    # verification (as opposed to the resume ending up unchanged simply
    # because Agent 2 never proposed anything, or only "keep" no-ops)? This
    # is the real signal that the revision failed for lack of evidence, not
    # just that the resulting markdown happens to match the original.
    stripped_for_unverifiability = bool(unverifiable_ids) or bool(unsupported_keywords)

    if decision != "revise":
        has_reported_changes = bool(changes) or bool(added_keywords) or bool(
            removed_or_reduced_items
        )
        if has_reported_changes or not markdown_unchanged:
            markdown = current_resume
            changes = []
            added_keywords = []
            removed_or_reduced_items = []
            finalize_notes.append(
                f"Decision was {decision!r} but the output contained changes; "
                "reverted updated_resume_markdown to the original resume and "
                "cleared all reported changes for safety."
            )
    elif markdown_unchanged and stripped_for_unverifiability:
        decision = "keep_insufficient_fit"
        revision_summary = (
            "Automated note: the proposed changes could not be verified against "
            "truthful evidence, so this resume was left unchanged. "
            + revision_summary
        )
        finalize_notes.append(
            "Decision was 'revise' but every proposed change failed truthfulness "
            "verification; changed decision to 'keep_insufficient_fit' because no "
            "verifiable evidence supported strengthening this resume for the role."
        )
    elif not changes and markdown_unchanged:
        decision = "keep_already_strong"
        finalize_notes.append(
            "Decision was 'revise' but no actual changes were made; changed "
            "decision to 'keep_already_strong' to reflect what actually happened."
        )

    finalized = resume_revision.model_copy(
        update={
            "decision": decision,
            "updated_resume_markdown": markdown,
            "changes": changes,
            "added_keywords": added_keywords,
            "removed_or_reduced_items": removed_or_reduced_items,
            "evidence_used_from_coursework": evidence_used_from_coursework,
            "revision_summary": revision_summary,
        }
    )

    final_check = run_resume_revision_semantic_check(
        resume_revision=finalized,
        current_resume=current_resume,
        coursework_student_info=coursework_student_info,
    )
    final_confidence = compute_semantic_confidence(final_check)

    if finalize_notes:
        summary_note = (
            f"Deterministic validation automatically removed {len(finalize_notes)} "
            "unverifiable item(s) after repeated repair attempts failed."
        )
    else:
        summary_note = "Deterministic validation found no further automatic fixes to apply."

    return finalized.model_copy(
        update={
            "semantic_confidence": final_confidence,
            "semantic_warnings": (
                [summary_note] + finalize_notes + final_check.errors + final_check.warnings
            ),
        }
    )
