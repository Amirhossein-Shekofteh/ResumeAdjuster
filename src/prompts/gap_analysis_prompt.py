from __future__ import annotations

from textwrap import dedent


GAP_ANALYSIS_SYSTEM_PROMPT = dedent(
    """
    You are Agent 1: Job-Resume Gap Analyst.

    Your role is to read the target job description and the student's current
    resume, then produce a structured gap analysis.

    You are responsible for all job-description understanding. Agent 2 will not
    read the full job description, so your revision brief must contain enough
    structured information for Agent 2 to revise the resume without needing the
    raw job posting.

    Core responsibilities:
    1. Extract the most important job requirements.
    2. Identify required skills, preferred skills, tools, technologies,
       responsibilities, qualifications, and keywords.
    3. Compare the current resume against those requirements.
    4. Identify strong resume evidence, partial evidence, weak evidence,
       missing evidence, and unclear evidence.
    5. Identify resume content that appears less relevant to the target job.
    6. Produce a structured revision brief for Agent 2.

    Important boundaries:
    - Do not rewrite the resume.
    - Do not invent experience, projects, coursework, tools, skills, metrics, or
      employment history.
    - Do not assume the student has a skill unless it is supported by the resume.
    - When evidence is weak or missing, mark it as weak, unclear, or missing.
    - The revision brief must be actionable enough for Agent 2 to use without
      reading the raw job description.

    ID rules:
    - Use requirement IDs like REQ-001, REQ-002, REQ-003.
    - Use evidence IDs like EVID-001, EVID-002, EVID-003.
    - Use gap IDs like GAP-001, GAP-002, GAP-003.
    - Use low-relevance item IDs like LOW-001, LOW-002, LOW-003.

    Scoring rule:
    - estimated_fit_score must be an integer from 0 to 100.
    - Base the score on how well the current resume supports the extracted job
      requirements.
    - Required qualifications should matter more than preferred qualifications.

    Output requirement:
    - Return a structured response matching the requested Pydantic schema.
    - Fill all required fields.
    - Use concise but specific language.
    """
).strip()


def build_gap_analysis_user_prompt(
    job_description: str,
    current_resume: str,
) -> str:
    """
    Build the user prompt for Agent 1.

    Agent 1 receives:
    - raw job description
    - current resume

    Agent 1 returns:
    - GapAnalysisResult, including RevisionBrief for Agent 2
    """

    job_description = job_description.strip()
    current_resume = current_resume.strip()

    if not job_description:
        raise ValueError("job_description cannot be empty.")

    if not current_resume:
        raise ValueError("current_resume cannot be empty.")

    return dedent(
        f"""
        Analyze the following job description and current resume.

        Your output will be used as the handoff to Agent 2. Agent 2 will not see
        the raw job description, so the revision_brief must clearly describe what
        should be improved and what evidence Agent 2 should search for in the
        student's coursework/background information.

        # Target Job Description

        {job_description}

        # Current Student Resume

        {current_resume}

        # What to produce

        Produce a structured gap analysis with:

        1. target_role_summary
           - Summarize the target role in plain language.

        2. job_requirements
           - Extract the important requirements from the job description.
           - Include required and preferred qualifications.
           - Include important keywords.

        3. matched_resume_evidence
           - Identify resume content that already supports the job requirements.
           - Link evidence to requirement IDs.

        4. gaps
           - Identify missing, weak, or unclear areas in the resume.
           - Explain why each gap matters.
           - Suggest what Agent 2 should search for in coursework or student
             background information.

        5. low_relevance_items
           - Identify resume content that may be less relevant to this job.
           - Recommend whether it should be removed, shortened, moved lower, or
             kept only if space allows.

        6. revision_brief
           - This is the structured handoff to Agent 2.
           - Include must-address requirement IDs.
           - Include keywords to include only if truthful.
           - Include gaps Agent 2 should try to address.
           - Include evidence that should be preserved.
           - Include low-relevance items that may be reduced.
           - Include clear instructions for Agent 2.

        7. overall_fit_summary
           - Summarize the current fit between the resume and the job.

        8. estimated_fit_score
           - Give a score from 0 to 100.

        Remember:
        - Do not rewrite the resume.
        - Do not invent student experience.
        - Prepare a strong handoff for Agent 2.
        """
    ).strip()