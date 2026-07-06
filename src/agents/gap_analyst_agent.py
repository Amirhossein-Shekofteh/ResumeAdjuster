from __future__ import annotations

from src.llm_client import LLMClient, LLMClientError, generate_structured_response
from src.prompts.gap_analysis_prompt import (
    GAP_ANALYSIS_SYSTEM_PROMPT,
    build_gap_analysis_user_prompt,
)
from src.schemas import GapAnalysisResult


class GapAnalystAgentError(Exception):
    """
    Raised when Agent 1 fails to produce a valid gap analysis.
    """


class GapAnalystAgent:
    """
    Agent 1: Job-Resume Gap Analyst.

    This agent is responsible for:
    - reading the raw job description
    - reading the current resume
    - extracting job requirements
    - identifying resume gaps
    - identifying weak or missing evidence
    - identifying low-relevance resume content
    - producing the structured revision brief for Agent 2

    Agent 2 should not need the raw job description because this agent's
    RevisionBrief is the formal handoff.
    """

    agent_name = "Job-Resume Gap Analyst"

    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self.llm_client = llm_client

    def analyze(
        self,
        job_description: str,
        current_resume: str,
    ) -> GapAnalysisResult:
        """
        Run Agent 1 and return a structured GapAnalysisResult.
        """

        job_description = job_description.strip()
        current_resume = current_resume.strip()

        if not job_description:
            raise GapAnalystAgentError("job_description cannot be empty.")

        if not current_resume:
            raise GapAnalystAgentError("current_resume cannot be empty.")

        user_prompt = build_gap_analysis_user_prompt(
            job_description=job_description,
            current_resume=current_resume,
        )

        try:
            if self.llm_client is not None:
                return self.llm_client.invoke_structured(
                    system_prompt=GAP_ANALYSIS_SYSTEM_PROMPT,
                    user_prompt=user_prompt,
                    output_schema=GapAnalysisResult,
                )

            return generate_structured_response(
                system_prompt=GAP_ANALYSIS_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                output_schema=GapAnalysisResult,
            )

        except LLMClientError as exc:
            raise GapAnalystAgentError(
                f"{self.agent_name} failed during LLM execution: {exc}"
            ) from exc
        except Exception as exc:
            raise GapAnalystAgentError(
                f"{self.agent_name} failed: {exc}"
            ) from exc


def run_gap_analysis(
    job_description: str,
    current_resume: str,
    llm_client: LLMClient | None = None,
) -> GapAnalysisResult:
    """
    Convenience function for running Agent 1.

    This is the function LangGraph nodes should usually call.
    """

    agent = GapAnalystAgent(llm_client=llm_client)
    return agent.analyze(
        job_description=job_description,
        current_resume=current_resume,
    )