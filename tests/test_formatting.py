from __future__ import annotations

from src.schemas import ResumeChange
from src.utils.formatting import format_change_summary


def _change(change_id: str, change_type: str, **kwargs) -> ResumeChange:
    defaults = {
        "resume_section": "Skills",
        "before": None,
        "after": None,
        "reason": "Reason.",
        "evidence_source": "Original resume.",
    }
    defaults.update(kwargs)
    return ResumeChange(change_id=change_id, change_type=change_type, **defaults)


def test_no_changes_returns_placeholder() -> None:
    assert format_change_summary([]) == "_No resume changes were recorded._"


def test_groups_changes_by_kept_rewritten_added_removed() -> None:
    changes = [
        _change("CHG-001", "keep", reason="Already strong."),
        _change("CHG-002", "rewrite", before="Old bullet.", after="New bullet."),
        _change("CHG-003", "add", after="New bullet added."),
        _change("CHG-004", "remove", before="Old bullet removed."),
        _change("CHG-005", "reorder", reason="Moved higher for relevance."),
    ]

    summary = format_change_summary(changes)

    kept_index = summary.index("### Kept As-Is")
    rewritten_index = summary.index("### Rewritten")
    added_index = summary.index("### Added")
    removed_index = summary.index("### Removed")

    # Sections appear in a stable, predictable order.
    assert kept_index < rewritten_index < added_index < removed_index

    assert "CHG-001" in summary
    assert "CHG-002" in summary
    assert "CHG-003" in summary
    assert "CHG-004" in summary
    # "reorder" is grouped together with "rewrite" under "Rewritten".
    assert "CHG-005" in summary
    assert summary.count("### Rewritten") == 1

    # Kept section shouldn't contain the added/removed change IDs, and vice versa.
    kept_section = summary[kept_index:rewritten_index]
    assert "CHG-001" in kept_section
    assert "CHG-003" not in kept_section
    assert "CHG-004" not in kept_section


def test_omits_empty_groups() -> None:
    changes = [_change("CHG-001", "add", after="New bullet.")]

    summary = format_change_summary(changes)

    assert "### Added" in summary
    assert "### Kept As-Is" not in summary
    assert "### Rewritten" not in summary
    assert "### Removed" not in summary


def test_auto_removed_change_is_visible_and_labeled() -> None:
    changes = [
        _change(
            "AUTO-REMOVE-KEYWORD-1",
            "remove",
            resume_section="(automated validation)",
            before="Kubernetes",
            reason=(
                "Automatically removed: not supported by the resume or "
                "coursework/student background information."
            ),
            evidence_source="Deterministic semantic validation.",
        )
    ]

    summary = format_change_summary(changes)

    assert "### Removed" in summary
    assert "Automatically removed" in summary
    assert "Kubernetes" in summary
