from __future__ import annotations

import json
from textwrap import dedent
from typing import Any


RESUME_REVISION_SYSTEM_PROMPT = dedent(
    """
    You are Agent 2: Resume Revision Agent.

    Your role is to revise the student's resume using:
    1. The student's current resume.
    2. The student's coursework and related background information.
    3. The structured revision brief produced by Agent 1.

    You do not receive the raw job description. Do not ask for it. Do not try to
    re-analyze the job posting. Trust Agent 1's structured revision brief as the
    source of job-targeting guidance.

    Core responsibilities:
    1. Read the current resume.
    2. Read the coursework and student background information.
    3. Read Agent 1's structured revision brief.
    4. Determine which gaps can be truthfully addressed using the student's
       coursework, projects, tools, labs, class assignments, certifications,
       student work, or related background.
    5. Replace or reduce less relevant resume content when stronger relevant
       evidence exists.
    6. Rewrite resume bullets to better align with the target role.
    7. Produce a complete updated resume in Markdown.
    8. Explain all meaningful changes.

    Strict truthfulness rules:
    - Do not invent experience.
    - Do not invent employers.
    - Do not invent projects.
    - Do not invent coursework.
    - Do not invent technical tools, programming languages, metrics, awards, or
      certifications.
    - Do not add a keyword unless it is supported by the original resume or the
      coursework/student background information.
    - If a gap cannot be filled truthfully, include it as a warning instead of
      hiding it.

    Revision rules:
    - Preserve strong relevant evidence from the original resume.
    - Use coursework or student background information only when it is relevant
      and truthful.
    - Prefer replacing low-relevance content with stronger job-relevant evidence.
    - Keep the resume concise and student-appropriate.
    - Use action-oriented resume bullets.
    - Do not overstate the student's level of experience.
    - Keep the final resume realistic for a student or early-career applicant.

    Output requirement:
    - Return a structured response matching the requested Pydantic schema.
    - Fill all required fields.
    - updated_resume_markdown must contain the full revised resume.
    """
).strip()


def _serialize_revision_brief(revision_brief: Any) -> str:
    """
    Convert Agent 1's revision brief into prompt-ready text.

    Supports:
    - Pydantic models
    - dictionaries
    - plain strings
    """

    if revision_brief is None:
        raise ValueError("revision_brief cannot be None.")

    if isinstance(revision_brief, str):
        revision_brief = revision_brief.strip()

        if not revision_brief:
            raise ValueError("revision_brief cannot be empty.")

        return revision_brief

    if hasattr(revision_brief, "model_dump"):
        return json.dumps(
            revision_brief.model_dump(mode="json"),
            indent=2,
            ensure_ascii=False,
        )

    if isinstance(revision_brief, dict):
        return json.dumps(
            revision_brief,
            indent=2,
            ensure_ascii=False,
        )

    raise TypeError(
        "revision_brief must be a string, dictionary, or Pydantic model. "
        f"Got {type(revision_brief).__name__}."
    )


def build_resume_revision_user_prompt(
    current_resume: str,
    coursework_student_info: str,
    revision_brief: Any,
) -> str:
    """
    Build the user prompt for Agent 2.

    Agent 2 receives:
    - current resume
    - coursework/student background information
    - Agent 1's revision brief

    Agent 2 does not receive the raw job description.
    """

    current_resume = current_resume.strip()
    coursework_student_info = coursework_student_info.strip()
    serialized_revision_brief = _serialize_revision_brief(revision_brief)

    if not current_resume:
        raise ValueError("current_resume cannot be empty.")

    if not coursework_student_info:
        raise ValueError("coursework_student_info cannot be empty.")

    return dedent(
        f"""
        Revise the student's resume using only the information below.

        You do not have the raw job description. Do not request it and do not
        recreate it. Use Agent 1's revision brief as the job-targeting guide.

        # Current Student Resume

        {current_resume}

        # Coursework and Student Background Information

        {coursework_student_info}

        # Agent 1 Revision Brief

        {serialized_revision_brief}

        # What to produce

        Produce a structured resume revision with:

        1. updated_resume_markdown
           - Full revised resume in Markdown.
           - Keep it concise, readable, and appropriate for a student applicant.

        2. changes
           - List each meaningful change.
           - Include what changed, where it changed, why it changed, and what
             evidence supports it.

        3. added_keywords
           - List only keywords that were added truthfully.
           - Every added keyword must be supported by the original resume or the
             coursework/student background information.

        4. removed_or_reduced_items
           - List content that was removed, shortened, or de-emphasized.

        5. evidence_used_from_coursework
           - List coursework, projects, assignments, labs, tools, or background
             details used to strengthen the resume.

        6. warnings
           - List gaps that could not be filled truthfully.
           - List any requirements from the revision brief that still lack
             evidence.

        7. revision_summary
           - Explain the overall revision strategy in plain language.

        Remember:
        - Do not invent anything.
        - Do not add unsupported skills.
        - Do not exaggerate the student's experience.
        - Replace less relevant content only when stronger relevant evidence is
          available.
        """
    ).strip()