from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


SemanticStatus = Literal["pass", "warning", "fail"]


@dataclass(frozen=True)
class SemanticCheckResult:
    """
    Deterministic semantic check result.

    Shared shape for any non-LLM agent-output checker in the workflow (Agent 1
    today, Agent 2 later). It only checks grounding/referential integrity, not
    writing quality.
    """

    status: SemanticStatus
    passed: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    total_checks: int = 0
    failed_checks: int = 0


def compute_semantic_confidence(check: SemanticCheckResult) -> int:
    """
    Compute a deterministic 0-100 confidence score from a SemanticCheckResult.

    Based on the ratio of failed to total atomic checks, with a small extra
    penalty per warning. No LLM involved.
    """

    if check.total_checks == 0:
        return 100

    score = round(100 * (1 - check.failed_checks / check.total_checks))
    score -= min(10, 2 * len(check.warnings))

    return max(0, min(100, score))
