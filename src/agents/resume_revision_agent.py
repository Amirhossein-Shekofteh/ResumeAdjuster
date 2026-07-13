from __future__ import annotations

from typing import Any

from src.llm_client import LLMClient, LLMClientError, generate_structured_response
from src.prompts.resume_revision_prompt import (
    RESUME_REVISION_SYSTEM_PROMPT,
    build_resume_revision_repair_user_prompt,
    build_resume_revision_user_prompt,
)
from src.schemas import ResumeRevisionResult, RevisionBrief


class ResumeRevisionAgentError(Exception):
    """
    Raised when Agent 2 fails to produce a valid resume revision.
    """


class ResumeRevisionAgent:
    """
    Agent 2: Resume Revision Agent.

    This agent is responsible for:
    - reading the current resume
    - reading coursework and student background information
    - reading Agent 1's structured revision brief
    - revising the resume truthfully
    - replacing or reducing low-relevance resume content when stronger evidence exists
    - explaining all meaningful changes

    Important boundary:
    - This agent does not receive the raw job description.
    - It uses Agent 1's RevisionBrief as the job-targeting handoff.
    """

    agent_name = "Resume Revision Agent"

    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self.llm_client = llm_client

    def revise(
        self,
        current_resume: str,
        coursework_student_info: str,
        revision_brief: RevisionBrief | dict[str, Any] | str,
    ) -> ResumeRevisionResult:
        """
        Run Agent 2 and return a structured ResumeRevisionResult.
        """

        current_resume = current_resume.strip()
        coursework_student_info = coursework_student_info.strip()

        if not current_resume:
            raise ResumeRevisionAgentError("current_resume cannot be empty.")

        if not coursework_student_info:
            raise ResumeRevisionAgentError(
                "coursework_student_info cannot be empty."
            )

        if revision_brief is None:
            raise ResumeRevisionAgentError("revision_brief cannot be None.")

        user_prompt = build_resume_revision_user_prompt(
            current_resume=current_resume,
            coursework_student_info=coursework_student_info,
            revision_brief=revision_brief,
        )

        try:
            if self.llm_client is not None:
                return self.llm_client.invoke_structured(
                    system_prompt=RESUME_REVISION_SYSTEM_PROMPT,
                    user_prompt=user_prompt,
                    output_schema=ResumeRevisionResult,
                )

            return generate_structured_response(
                system_prompt=RESUME_REVISION_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                output_schema=ResumeRevisionResult,
            )

        except LLMClientError as exc:
            raise ResumeRevisionAgentError(
                f"{self.agent_name} failed during LLM execution: {exc}"
            ) from exc
        except Exception as exc:
            raise ResumeRevisionAgentError(
                f"{self.agent_name} failed: {exc}"
            ) from exc

    def repair(
        self,
        current_resume: str,
        coursework_student_info: str,
        revision_brief: RevisionBrief | dict[str, Any] | str,
        previous_result: ResumeRevisionResult,
        validation_errors: list[str],
    ) -> ResumeRevisionResult:
        """
        Re-run Agent 2, asking it to fix deterministic validation errors found
        in a previous ResumeRevisionResult.
        """

        current_resume = current_resume.strip()
        coursework_student_info = coursework_student_info.strip()

        if not current_resume:
            raise ResumeRevisionAgentError("current_resume cannot be empty.")

        if not coursework_student_info:
            raise ResumeRevisionAgentError(
                "coursework_student_info cannot be empty."
            )

        if revision_brief is None:
            raise ResumeRevisionAgentError("revision_brief cannot be None.")

        user_prompt = build_resume_revision_repair_user_prompt(
            current_resume=current_resume,
            coursework_student_info=coursework_student_info,
            revision_brief=revision_brief,
            previous_result=previous_result,
            validation_errors=validation_errors,
        )

        try:
            if self.llm_client is not None:
                return self.llm_client.invoke_structured(
                    system_prompt=RESUME_REVISION_SYSTEM_PROMPT,
                    user_prompt=user_prompt,
                    output_schema=ResumeRevisionResult,
                )

            return generate_structured_response(
                system_prompt=RESUME_REVISION_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                output_schema=ResumeRevisionResult,
            )

        except LLMClientError as exc:
            raise ResumeRevisionAgentError(
                f"{self.agent_name} failed during LLM execution: {exc}"
            ) from exc
        except Exception as exc:
            raise ResumeRevisionAgentError(
                f"{self.agent_name} failed: {exc}"
            ) from exc


def run_resume_revision(
    current_resume: str,
    coursework_student_info: str,
    revision_brief: RevisionBrief | dict[str, Any] | str,
    llm_client: LLMClient | None = None,
) -> ResumeRevisionResult:
    """
    Convenience function for running Agent 2.

    This is the function LangGraph nodes should usually call.

    Agent 2 intentionally does not accept job_description as an argument.
    """

    agent = ResumeRevisionAgent(llm_client=llm_client)
    return agent.revise(
        current_resume=current_resume,
        coursework_student_info=coursework_student_info,
        revision_brief=revision_brief,
    )


def run_resume_revision_repair(
    current_resume: str,
    coursework_student_info: str,
    revision_brief: RevisionBrief | dict[str, Any] | str,
    previous_result: ResumeRevisionResult,
    validation_errors: list[str],
    llm_client: LLMClient | None = None,
) -> ResumeRevisionResult:
    """
    Convenience function for running Agent 2's repair path.

    This is the function LangGraph nodes should usually call.
    """

    agent = ResumeRevisionAgent(llm_client=llm_client)
    return agent.repair(
        current_resume=current_resume,
        coursework_student_info=coursework_student_info,
        revision_brief=revision_brief,
        previous_result=previous_result,
        validation_errors=validation_errors,
    )