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

    The revision brief includes gap_analysis_confidence (0-100) and
    gap_analysis_semantic_warnings, produced by a deterministic validator of
    Agent 1's output. If gap_analysis_confidence is below 100, treat the items
    listed in gap_analysis_semantic_warnings as unverified: do not rely on them
    as trustworthy evidence, and lean more heavily on the current resume and
    coursework/student background information you were given directly.

    The revision brief also includes estimated_fit_score (0-100, deterministic)
    and overall_fit_summary, both computed by Agent 1. Use them as signals when
    deciding whether a revision is worthwhile, alongside gaps_to_address and
    resume_evidence_to_preserve.

    Before writing anything, do a per-gap review: go through every gap in
    revision_brief.gaps_to_address one at a time, and for each one, check
    whether the current resume or the coursework/student background
    information contains truthful evidence that closes it, fully or
    partially. Note which gaps have real supporting evidence and which do
    not -- especially any tied to must_address_requirement_ids. Do not skip
    this step or judge fit only from estimated_fit_score in the abstract;
    the per-gap review is what your decision must actually be based on.

    Only after that per-gap review, decide which of three outcomes applies,
    and set the `decision` field accordingly:
    - "revise": the per-gap review found truthful evidence, in the current
      resume or the coursework/student background information, that can
      meaningfully strengthen the resume for at least one gap. This is the
      common case.
    - "keep_already_strong": resume_evidence_to_preserve and a high
      estimated_fit_score indicate the resume already fits this role well,
      and the per-gap review did not surface any truthful change that would
      meaningfully improve it.
    - "keep_insufficient_fit": the gaps_to_address are significant (especially
      any tied to must_address_requirement_ids), and the per-gap review found
      that neither the current resume nor the coursework/student background
      information gives you truthful material to close them. Revising would
      require fabricating or stretching evidence, so it is more honest to
      leave the resume unchanged and tell the student why.

    Hard rule for "keep_already_strong" and "keep_insufficient_fit": you must
    return updated_resume_markdown exactly as the original current resume,
    unchanged, and changes, added_keywords, and removed_or_reduced_items must
    all be empty. Use revision_summary to explain, in plain language, which of
    the two "keep" outcomes applies and why (referencing the fit score,
    fit summary, or specific gaps as appropriate) -- for these two outcomes,
    revision_summary is your explanation of the decision, not a change log.

    Core responsibilities:
    1. Read the current resume.
    2. Read Agent 1's structured revision brief, in particular
       gaps_to_address and must_address_requirement_ids.
    3. Read the coursework and student background information, checking it
       against each gap from the brief (the per-gap review described above).
    4. Determine which gaps can be truthfully addressed using the student's
       coursework, projects, tools, labs, class assignments, certifications,
       student work, or related background.
    5. Replace or reduce less relevant resume content when stronger relevant
       evidence exists.
    6. Rewrite resume bullets to better align with the target role.
    7. Produce a complete updated resume in Markdown.
    8. Explain all meaningful changes, including content you deliberately kept
       unchanged (see the `changes` rule below).

    Strict truthfulness rules:
    - Do not invent experience.
    - Do not invent employers.
    - Do not invent projects.
    - Do not invent coursework.
    - Do not invent technical tools, programming languages, metrics, awards, or
      certifications.
    - Do not add a keyword unless it is supported by the original resume or the
      coursework/student background information.
    - Every add/rewrite change's evidence_source must be an exact, verbatim quote
      copied from the current resume or the coursework/student background
      information -- never a category label like "original resume" or
      "coursework info". A deterministic validator checks that this exact text
      appears in one of those two source texts, so a label instead of a real
      quote will be rejected as unverifiable.
    - If you cannot find a genuine verbatim quote to justify a proposed change,
      do not make that change. If dropping every change that lacks real
      evidence leaves nothing meaningful to revise, set decision to
      "keep_insufficient_fit" instead of keeping a weakly-supported change.
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

        # Agent 1 Revision Brief

        {serialized_revision_brief}

        # Coursework and Student Background Information

        Read the gaps_to_address and must_address_requirement_ids above
        first, then use this section to do the per-gap review: for each gap,
        check whether the information below contains truthful evidence that
        closes it.

        {coursework_student_info}

        # What to produce

        Produce a structured resume revision with:

        1. decision
           - "revise", "keep_already_strong", or "keep_insufficient_fit" (see
             the system prompt for when to use each).
           - If not "revise", updated_resume_markdown must equal the original
             current resume exactly, and changes, added_keywords, and
             removed_or_reduced_items must all be empty.

        2. updated_resume_markdown
           - Full revised resume in Markdown.
           - Keep it concise, readable, and appropriate for a student applicant.

        3. changes
           - List each meaningful change (change_type: add, remove, rewrite, or
             reorder). Include what changed, where it changed, why it changed,
             and what evidence supports it.
           - For every add/rewrite change, evidence_source must be an exact,
             verbatim quote copied from the current resume or the coursework/
             student background information above -- not a category label. If
             you cannot copy a real quote that truthfully supports the change,
             drop the change instead of inventing a label for it.
           - Also list the major resume sections/bullets you deliberately kept
             unchanged, as changes with change_type "keep" (before and after
             identical, reason explaining why it was already strong). Together
             with the edits above, `changes` should read as a complete map of
             the resume: what was kept, what was rewritten, what was added,
             and what was removed -- not only a list of edits.

        4. added_keywords
           - List only keywords that were added truthfully.
           - Every added keyword must be supported by the original resume or the
             coursework/student background information.

        5. removed_or_reduced_items
           - List content that was removed, shortened, or de-emphasized.

        6. evidence_used_from_coursework
           - List coursework, projects, assignments, labs, tools, or background
             details used to strengthen the resume.

        7. warnings
           - List gaps that could not be filled truthfully.
           - List any requirements from the revision brief that still lack
             evidence.

        8. revision_summary
           - If decision is "revise", explain the overall revision strategy in
             plain language.
           - If decision is "keep_already_strong" or "keep_insufficient_fit",
             explain why in plain language instead.

        Remember:
        - Do not invent anything.
        - Do not add unsupported skills.
        - Do not exaggerate the student's experience.
        - Replace less relevant content only when stronger relevant evidence is
          available.
        - A deterministic validator will check every added_keywords entry
          against the current resume and coursework/student background
          information, and will reject any added_keywords entry it cannot
          find in updated_resume_markdown. Only claim a keyword was added if
          it is truthfully supported and actually present in the final resume.
        - The same validator will check every add/rewrite change's
          evidence_source against the current resume and coursework/student
          background information, and will reject it if that text is not an
          exact quote found in one of those two sources. If you cannot produce
          a real quote, do not make that change.
        - If, after dropping every change that lacks a real supporting quote,
          nothing meaningful remains to revise, set decision to
          "keep_insufficient_fit" and explain why in revision_summary instead
          of shipping unsupported changes.
        """
    ).strip()


def build_resume_revision_repair_user_prompt(
    current_resume: str,
    coursework_student_info: str,
    revision_brief: Any,
    previous_result: Any,
    validation_errors: list[str],
) -> str:
    """
    Build the repair user prompt for Agent 2.

    Used when a deterministic semantic check found self-consistency or
    truthfulness problems in a previous ResumeRevisionResult. Agent 2 must
    return a full corrected result, not a diff.
    """

    current_resume = current_resume.strip()
    coursework_student_info = coursework_student_info.strip()
    serialized_revision_brief = _serialize_revision_brief(revision_brief)

    if not current_resume:
        raise ValueError("current_resume cannot be empty.")

    if not coursework_student_info:
        raise ValueError("coursework_student_info cannot be empty.")

    if not validation_errors:
        raise ValueError("validation_errors cannot be empty.")

    previous_result_json = previous_result.model_dump_json(indent=2)
    errors_list = "\n".join(f"- {error}" for error in validation_errors)

    return dedent(
        f"""
        Your previous resume revision failed deterministic validation. Produce
        a corrected, complete resume revision that fixes every issue below.

        # Current Student Resume

        {current_resume}

        # Coursework and Student Background Information

        {coursework_student_info}

        # Agent 1 Revision Brief

        {serialized_revision_brief}

        # Your Previous Output

        {previous_result_json}

        # Validation Errors To Fix

        {errors_list}

        # What to produce

        - Return a full, corrected ResumeRevisionResult matching the schema,
          not a diff or partial update.
        - The `decision` field must be consistent with the rest of the output:
          if decision is "keep_already_strong" or "keep_insufficient_fit",
          updated_resume_markdown must equal the original current resume
          exactly, and changes, added_keywords, and removed_or_reduced_items
          must all be empty. If the previous output's decision does not match
          what the output actually contains, fix whichever one is wrong so
          they agree.
        - Every add/rewrite change's `after` text must actually appear in
          updated_resume_markdown, and its evidence_source must be an exact,
          verbatim quote copied from the current resume or the coursework/
          student background information above -- not a category label like
          "original resume" or "coursework info". If you cannot copy a real
          quote that truthfully supports a change, remove that change rather
          than inventing a label for it.
        - Every remove change's `before` text must no longer appear anywhere
          in updated_resume_markdown.
        - Every added_keywords entry must actually appear in
          updated_resume_markdown, and must be genuinely supported by the
          current resume or the coursework/student background information
          above. If you cannot verify a keyword, remove it rather than keep
          claiming it.
        - Every evidence_used_from_coursework entry must be genuinely found in
          the coursework/student background information above.
        - Do not introduce duplicate change_id values.
        - If removing every change that lacks a real supporting quote leaves
          nothing meaningful to revise, switch decision to
          "keep_insufficient_fit", set updated_resume_markdown back to the
          original current resume, clear changes/added_keywords/
          removed_or_reduced_items, and explain why in revision_summary --
          do not keep a "revise" decision propped up by unverifiable evidence.
        - Preserve everything from your previous output that was already
          correct; only change what is needed to fix the validation errors.
        """
    ).strip()