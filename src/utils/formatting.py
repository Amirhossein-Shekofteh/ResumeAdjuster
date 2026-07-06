from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from src.schemas import GapItem, JobRequirement, ResumeChange


def clean_display_text(value: Any) -> str:
    """
    Convert a value into clean display text.
    """

    if value is None:
        return ""

    text = str(value).strip()
    return " ".join(text.split())


def escape_markdown_table_cell(value: Any) -> str:
    """
    Escape text for use inside a Markdown table cell.
    """

    text = clean_display_text(value)
    text = text.replace("|", "\\|")
    text = text.replace("\n", "<br>")
    return text


def format_markdown_list(items: Iterable[Any]) -> str:
    """
    Convert a list of values into a Markdown bullet list.
    """

    cleaned_items = [clean_display_text(item) for item in items]
    cleaned_items = [item for item in cleaned_items if item]

    if not cleaned_items:
        return "_None._"

    return "\n".join(f"- {item}" for item in cleaned_items)


def format_numbered_list(items: Iterable[Any]) -> str:
    """
    Convert a list of values into a Markdown numbered list.
    """

    cleaned_items = [clean_display_text(item) for item in items]
    cleaned_items = [item for item in cleaned_items if item]

    if not cleaned_items:
        return "_None._"

    return "\n".join(
        f"{index}. {item}"
        for index, item in enumerate(cleaned_items, start=1)
    )


def format_keyword_list(keywords: Iterable[str]) -> str:
    """
    Format keywords as inline code-style Markdown items.
    """

    cleaned_keywords = [clean_display_text(keyword) for keyword in keywords]
    cleaned_keywords = [keyword for keyword in cleaned_keywords if keyword]

    if not cleaned_keywords:
        return "_No keywords added._"

    return ", ".join(f"`{keyword}`" for keyword in cleaned_keywords)


def format_warning_list(warnings: Iterable[str]) -> str:
    """
    Format warnings or errors as a Markdown bullet list.
    """

    cleaned_warnings = [clean_display_text(warning) for warning in warnings]
    cleaned_warnings = [warning for warning in cleaned_warnings if warning]

    if not cleaned_warnings:
        return "_No warnings._"

    return "\n".join(f"- ⚠️ {warning}" for warning in cleaned_warnings)


def format_fit_score(score: int | None) -> str:
    """
    Format a 0-100 fit score with a plain-language label.
    """

    if score is None:
        return "_No fit score available._"

    if score < 0 or score > 100:
        return f"`{score}/100` — invalid score"

    if score >= 80:
        label = "Strong fit"
    elif score >= 60:
        label = "Moderate fit"
    elif score >= 40:
        label = "Partial fit"
    else:
        label = "Low fit"

    return f"**{score}/100** — {label}"


def format_requirements_table(requirements: Iterable[JobRequirement]) -> str:
    """
    Format job requirements as a Markdown table.
    """

    requirements = list(requirements)

    if not requirements:
        return "_No job requirements extracted._"

    lines = [
        "| ID | Priority | Category | Requirement | Keywords |",
        "|---|---|---|---|---|",
    ]

    for requirement in requirements:
        keywords = ", ".join(requirement.keywords)

        lines.append(
            "| "
            + " | ".join(
                [
                    escape_markdown_table_cell(requirement.requirement_id),
                    escape_markdown_table_cell(requirement.priority),
                    escape_markdown_table_cell(requirement.category),
                    escape_markdown_table_cell(requirement.description),
                    escape_markdown_table_cell(keywords),
                ]
            )
            + " |"
        )

    return "\n".join(lines)


def format_gap_table(gaps: Iterable[GapItem]) -> str:
    """
    Format resume gaps as a Markdown table.
    """

    gaps = list(gaps)

    if not gaps:
        return "_No major resume gaps identified._"

    lines = [
        "| ID | Requirement | Type | Severity | Gap | Why It Matters |",
        "|---|---|---|---|---|---|",
    ]

    for gap in gaps:
        lines.append(
            "| "
            + " | ".join(
                [
                    escape_markdown_table_cell(gap.gap_id),
                    escape_markdown_table_cell(gap.requirement_id),
                    escape_markdown_table_cell(gap.gap_type),
                    escape_markdown_table_cell(gap.severity),
                    escape_markdown_table_cell(gap.description),
                    escape_markdown_table_cell(gap.why_it_matters),
                ]
            )
            + " |"
        )

    return "\n".join(lines)


def format_change_summary(changes: Iterable[ResumeChange]) -> str:
    """
    Format resume changes into a readable Markdown list.
    """

    changes = list(changes)

    if not changes:
        return "_No resume changes were recorded._"

    lines: list[str] = []

    for change in changes:
        block: list[str] = [
            f"- **{change.change_id} — {change.change_type.upper()}**",
            f"  - Section: {change.resume_section}",
            f"  - Reason: {change.reason}",
            f"  - Evidence source: {change.evidence_source}",
        ]

        if change.before:
            block.append(f"  - Before: {change.before}")

        if change.after:
            block.append(f"  - After: {change.after}")

        lines.append("\n".join(block))

    return "\n".join(lines)


def truncate_display_text(text: str, max_length: int = 300) -> str:
    """
    Truncate long display text without affecting the original source data.
    """

    text = clean_display_text(text)

    if max_length <= 0:
        raise ValueError("max_length must be greater than 0.")

    if len(text) <= max_length:
        return text

    return text[: max_length - 3].rstrip() + "..."