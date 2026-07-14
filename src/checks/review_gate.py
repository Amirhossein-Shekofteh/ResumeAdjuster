from __future__ import annotations

import re

from src.checks.semantic_check_result import SemanticCheckResult
from src.schemas import GapAnalysisResult, ResumeRevisionResult, ReviewGateResult


_PROMPT_INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?previous\s+instructions",
    r"disregard\s+(all\s+)?previous\s+instructions",
    r"reveal\s+(the\s+)?system\s+prompt",
    r"developer\s+message",
    r"system\s+message",
    r"add\s+fake",
    r"fabricate",
    r"make\s+up",
    r"pretend\s+I\s+have",
    r"you\s+are\s+now",
    r"forget\s+your\s+instructions",
]

# Narrower subset of the patterns above, used only to scan an agent's OWN
# generated output (RevisionBrief text, Agent 2's resume/summary/warnings) for
# leaked/laundered instructions. Deliberately excludes generic truthfulness
# vocabulary ("fabricate", "make up", "add fake") that the agents are
# explicitly prompted to use when explaining a truthful refusal to fabricate
# content (see resume_revision_prompt.py) -- matching on that vocabulary here
# produced false-positive blockers on honest output.
_INSTRUCTION_HIJACK_PATTERNS = [
    r"ignore\s+(all\s+)?previous\s+instructions",
    r"disregard\s+(all\s+)?previous\s+instructions",
    r"reveal\s+(the\s+)?system\s+prompt",
    r"developer\s+message",
    r"system\s+message",
    r"pretend\s+I\s+have",
    r"you\s+are\s+now",
    r"forget\s+your\s+instructions",
]

_OUT_OF_SCOPE_EVIDENCE_SOURCE_PATTERNS = [
    r"job\s+description",
    r"job\s+posting",
]

_OUT_OF_SCOPE_ACTION_PATTERNS = [
    r"\b(i\s+have\s+|i've\s+)?submitted\b",
    r"\bsent\s+the\s+(email|application)\b",
    r"\bapplied\s+on\s+your\s+behalf\b",
    r"\buploaded\s+the\s+resume\b",
    r"\be-?mailed\s+the\s+employer\b",
]

_INTERNAL_ID_LEAK_PATTERN = r"\b(REQ|GAP)-\d+\b"

_SCOPE_CREEP_PHRASES = ["final resume", "revised resume", "resume draft"]


def _contains_any(text: str | None, patterns: list[str]) -> bool:
    value = text or ""

    return any(re.search(pattern, value, flags=re.IGNORECASE) for pattern in patterns)


def _contains_prompt_injection_like_text(text: str | None) -> bool:
    return _contains_any(text, _PROMPT_INJECTION_PATTERNS)


def _contains_instruction_hijack_text(text: str | None) -> bool:
    return _contains_any(text, _INSTRUCTION_HIJACK_PATTERNS)


def _finalize_review(
    *,
    stage: str,
    blockers: list[str],
    warnings: list[str],
    human_review_required: bool,
    human_review_reason: str | None,
    policy_notes: list[str],
) -> ReviewGateResult:
    if blockers:
        verdict = "blocked"
        passed = False
    elif warnings or human_review_required:
        verdict = "needs_human_review"
        passed = True
    else:
        verdict = "approved"
        passed = True

    return ReviewGateResult(
        stage=stage,  # type: ignore[arg-type]
        verdict=verdict,  # type: ignore[arg-type]
        passed=passed,
        blockers=blockers,
        warnings=warnings,
        human_review_required=human_review_required,
        human_review_reason=human_review_reason,
        policy_notes=policy_notes,
    )


def run_agent1_review_gate(
    *,
    gap_analysis: GapAnalysisResult | None,
    semantic_check: SemanticCheckResult | None,
    job_description: str,
    current_resume: str,
) -> ReviewGateResult:
    """
    Reviewer gate for Agent 1: Job-Resume Gap Analyst.

    Checks whether Agent 1 stayed inside its scope (gap analysis and the
    RevisionBrief handoff) rather than whether its claims are grounded --
    the semantic checker already covers grounding.
    """

    blockers: list[str] = []
    warnings: list[str] = []
    policy_notes: list[str] = [
        "Agent 1 may use only the job description and current resume.",
        "Agent 1 owns job understanding, gap analysis, matched resume evidence, "
        "and the structured RevisionBrief.",
        "Agent 1 must not revise the resume or use coursework/student background.",
    ]

    if gap_analysis is None:
        blockers.append("Agent 1 produced no GapAnalysisResult.")

        return _finalize_review(
            stage="agent_1_gap_analysis",
            blockers=blockers,
            warnings=warnings,
            human_review_required=False,
            human_review_reason=None,
            policy_notes=policy_notes,
        )

    revision_brief = gap_analysis.revision_brief

    if revision_brief is None:
        blockers.append("Agent 1 did not produce a RevisionBrief for Agent 2.")
    else:
        if _contains_instruction_hijack_text(
            revision_brief.target_role_summary
        ) or any(
            _contains_instruction_hijack_text(instruction)
            for instruction in revision_brief.instructions_for_revision_agent
        ):
            blockers.append(
                "Prompt-injection-like text was found in the RevisionBrief that "
                "Agent 2 will trust without re-checking. Agent 2 must not receive "
                "laundered instructions from the job description or resume."
            )

        if (
            not revision_brief.instructions_for_revision_agent
            and not revision_brief.gaps_to_address
            and not revision_brief.resume_evidence_to_preserve
        ):
            warnings.append(
                "The RevisionBrief has no instructions, gaps, or evidence to preserve. "
                "The handoff to Agent 2 may be too thin to act on."
            )

    if _contains_prompt_injection_like_text(job_description) or _contains_prompt_injection_like_text(
        current_resume
    ):
        warnings.append(
            "Prompt-injection-like text detected in the uploaded job description or "
            "resume. Treat uploaded documents as data only, not instructions."
        )

    scope_creep_texts = [gap_analysis.target_role_summary, gap_analysis.overall_fit_summary]
    scope_creep_texts.extend(
        requirement.description for requirement in gap_analysis.job_requirements
    )
    scope_creep_texts.extend(gap.description for gap in gap_analysis.gaps)
    scope_creep_texts.extend(item.reason for item in gap_analysis.low_relevance_items)

    if any(_contains_any(text, _SCOPE_CREEP_PHRASES) for text in scope_creep_texts):
        warnings.append(
            "Agent 1 output appears to include final-resume language. Agent 1 should "
            "analyze gaps and create a RevisionBrief, not draft the resume itself."
        )

    if semantic_check is not None and not semantic_check.passed:
        warnings.append(
            "Agent 1's semantic check did not pass; the RevisionBrief carries a "
            "reduced gap_analysis_confidence score for Agent 2 to treat conservatively."
        )

    return _finalize_review(
        stage="agent_1_gap_analysis",
        blockers=blockers,
        warnings=warnings,
        human_review_required=False,
        human_review_reason=None,
        policy_notes=policy_notes,
    )


def run_agent2_review_gate(
    *,
    resume_revision: ResumeRevisionResult | None,
    semantic_check: SemanticCheckResult | None,
    current_resume: str,
    coursework_student_info: str,
) -> ReviewGateResult:
    """
    Reviewer gate for Agent 2: Resume Revision Agent.

    Checks whether Agent 2 stayed inside its scope (resume revision only)
    rather than whether its claims are grounded -- the semantic checker
    already covers truthfulness/grounding.
    """

    blockers: list[str] = []
    warnings: list[str] = []
    policy_notes: list[str] = [
        "Agent 2 may use only the current resume, coursework/student background, "
        "and Agent 1's RevisionBrief.",
        "Agent 2 must not receive the raw job description.",
        "The output is a resume draft only. The student must review and approve it "
        "before use.",
    ]

    if resume_revision is None:
        blockers.append("Agent 2 produced no ResumeRevisionResult.")

        return _finalize_review(
            stage="agent_2_resume_revision",
            blockers=blockers,
            warnings=warnings,
            human_review_required=True,
            human_review_reason="Student must review the resume draft before using it.",
            policy_notes=policy_notes,
        )

    own_output_texts = [
        resume_revision.updated_resume_markdown,
        resume_revision.revision_summary,
        *resume_revision.warnings,
        *(change.reason for change in resume_revision.changes),
    ]

    if any(_contains_instruction_hijack_text(text) for text in own_output_texts):
        blockers.append(
            "The resume revision contains prompt-injection-like language. This "
            "suggests source instructions may have leaked into the output."
        )

    if any(
        _contains_any(change.evidence_source, _OUT_OF_SCOPE_EVIDENCE_SOURCE_PATTERNS)
        for change in resume_revision.changes
    ):
        blockers.append(
            "A change cites the job description as its evidence source, but Agent 2 "
            "never receives the raw job description. This is an impossible evidence "
            "claim and must be reviewed."
        )

    if any(_contains_any(text, _OUT_OF_SCOPE_ACTION_PATTERNS) for text in own_output_texts):
        blockers.append(
            "The output implies an external action was taken (e.g. submitting or "
            "sending something). ResumeAdjuster may only draft content; it must not "
            "act without explicit human approval."
        )

    if _contains_prompt_injection_like_text(current_resume) or _contains_prompt_injection_like_text(
        coursework_student_info
    ):
        warnings.append(
            "Prompt-injection-like text detected in the uploaded resume or "
            "coursework/student background information. Treat uploaded documents as "
            "data only, not instructions."
        )

    if any(
        _contains_any(text, [_INTERNAL_ID_LEAK_PATTERN])
        for text in (resume_revision.updated_resume_markdown, resume_revision.revision_summary)
    ):
        warnings.append(
            "Internal requirement/gap IDs from Agent 1's analysis appear in the "
            "resume text shown to the student. These should not be user-facing."
        )

    if semantic_check is not None and not semantic_check.passed:
        warnings.append(
            "Agent 2's semantic check did not pass after finalization; review the "
            "resume_revision.semantic_warnings for unresolved issues."
        )

    return _finalize_review(
        stage="agent_2_resume_revision",
        blockers=blockers,
        warnings=warnings,
        human_review_required=True,
        human_review_reason="Student must review the resume draft before using it.",
        policy_notes=policy_notes,
    )
