from __future__ import annotations

from typing import Any

from src.graph.builder import build_resume_adjuster_graph
from src.graph.runner import run_resume_adjuster
from src.schemas import (
    GapAnalysisResult,
    JobRequirement,
    ResumeChange,
    ResumeEvidence,
    ResumeRevisionResult,
    RevisionBrief,
)


def _sample_revision_brief() -> RevisionBrief:
    requirement = JobRequirement(
        requirement_id="REQ-001",
        description="Experience with Python for data analysis.",
        priority="required",
        category="technical skill",
        keywords=["Python", "data analysis"],
    )

    evidence = ResumeEvidence(
        evidence_id="EVID-001",
        resume_section="Projects",
        text="Built a Python project for analyzing student survey data.",
        supported_requirement_ids=["REQ-001"],
        strength="strong",
        explanation="The project directly supports the Python requirement.",
    )

    return RevisionBrief(
        target_role_summary="Entry-level data analyst role focused on Python.",
        must_address_requirement_ids=["REQ-001"],
        keywords_to_include_if_truthful=["Python", "data analysis"],
        gaps_to_address=[],
        resume_evidence_to_preserve=[evidence],
        low_relevance_items_to_reduce=[],
        instructions_for_revision_agent=[
            "Emphasize Python coursework and data analysis project evidence."
        ],
    )


def _sample_gap_analysis_result() -> GapAnalysisResult:
    revision_brief = _sample_revision_brief()

    return GapAnalysisResult(
        target_role_summary="Entry-level data analyst role focused on Python.",
        job_requirements=[
            JobRequirement(
                requirement_id="REQ-001",
                description="Experience with Python for data analysis.",
                priority="required",
                category="technical skill",
                keywords=["Python", "data analysis"],
            )
        ],
        matched_resume_evidence=revision_brief.resume_evidence_to_preserve,
        gaps=[],
        low_relevance_items=[],
        revision_brief=revision_brief,
        overall_fit_summary="The resume has some relevant Python evidence.",
        estimated_fit_score=70,
    )


def _sample_resume_revision_result() -> ResumeRevisionResult:
    return ResumeRevisionResult(
        updated_resume_markdown=(
            "# Student Name\n\n"
            "## Projects\n\n- Built a Python project to analyze student survey data.\n\n"
            "## Skills\n\n- Python\n- Data Analysis"
        ),
        changes=[
            ResumeChange(
                change_id="CHG-001",
                change_type="rewrite",
                resume_section="Projects",
                before="Worked on class project.",
                after="Built a Python project to analyze student survey data.",
                reason="The revised bullet is more specific and aligned with the revision brief.",
                evidence_source="Original resume and coursework/student background information.",
            )
        ],
        added_keywords=["Python", "Data Analysis"],
        removed_or_reduced_items=[],
        evidence_used_from_coursework=[
            "Python coursework",
            "data analysis project",
        ],
        warnings=[],
        revision_summary="Revised the resume to emphasize Python and data analysis.",
    )


def _sample_invalid_resume_revision_result() -> ResumeRevisionResult:
    """
    A resume revision that claims an added keyword ("Kubernetes") which is
    present in the markdown but not supported by the current resume or the
    coursework/student background information used in these tests, so the
    semantic checker will fail it as a hard truthfulness error.
    """

    return ResumeRevisionResult(
        updated_resume_markdown="# Student Name\n\n## Skills\n\n- Python\n- Kubernetes",
        changes=[
            ResumeChange(
                change_id="CHG-001",
                change_type="add",
                resume_section="Skills",
                before=None,
                after="Kubernetes",
                reason="Added Kubernetes as a skill.",
                evidence_source="Coursework records.",
            )
        ],
        added_keywords=["Python", "Kubernetes"],
        removed_or_reduced_items=[],
        evidence_used_from_coursework=[],
        warnings=[],
        revision_summary="Added Kubernetes as a new skill.",
    )


def test_workflow_can_be_built() -> None:
    graph = build_resume_adjuster_graph()

    assert graph is not None


def test_graph_has_expected_nodes() -> None:
    graph = build_resume_adjuster_graph()
    graph_view = graph.get_graph()

    node_names = set(graph_view.nodes.keys())

    assert "clean_inputs" in node_names
    assert "gap_analysis" in node_names
    assert "semantic_check" in node_names
    assert "gap_analysis_repair" in node_names
    assert "resume_revision" in node_names
    assert "resume_revision_semantic_check" in node_names
    assert "resume_revision_repair" in node_names
    assert "resume_revision_finalize" in node_names
    assert "final_output" in node_names


def test_runner_accepts_sample_input_with_mocked_agents(monkeypatch: Any) -> None:
    def fake_run_gap_analysis(
        job_description: str,
        current_resume: str,
        llm_client: Any = None,
    ) -> GapAnalysisResult:
        assert "Python" in job_description
        assert "Python" in current_resume
        return _sample_gap_analysis_result()

    def fake_run_resume_revision(
        current_resume: str,
        coursework_student_info: str,
        revision_brief: RevisionBrief,
        llm_client: Any = None,
    ) -> ResumeRevisionResult:
        assert "Python" in current_resume
        assert "coursework" in coursework_student_info.lower()
        assert revision_brief.target_role_summary
        return _sample_resume_revision_result()

    monkeypatch.setattr(
        "src.graph.nodes.run_gap_analysis",
        fake_run_gap_analysis,
    )
    monkeypatch.setattr(
        "src.graph.nodes.run_resume_revision",
        fake_run_resume_revision,
    )

    result = run_resume_adjuster(
        job_description="Data analyst internship requiring Python and data analysis skills.",
        current_resume=(
            "Student resume with Python project. Built a Python project for "
            "analyzing student survey data."
        ),
        coursework_student_info="Completed Python coursework and data analysis project.",
    )

    assert result.success is True
    assert result.gap_analysis is not None
    assert result.resume_revision is not None
    assert result.final_resume_markdown is not None
    assert "Python" in result.final_resume_markdown
    assert result.errors == []
    assert len(result.agent_trace) >= 4

    # This path should pass the semantic check cleanly on the first try, with
    # no repair needed.
    assert result.gap_analysis.revision_brief.gap_analysis_confidence == 100
    assert result.gap_analysis.revision_brief.gap_analysis_semantic_warnings == []
    assert result.resume_revision.semantic_confidence == 100
    assert result.resume_revision.semantic_warnings == []


def _sample_invalid_gap_analysis_result() -> GapAnalysisResult:
    """
    A gap analysis whose evidence quote does not appear in the resume used by
    these tests, so the semantic checker will fail it.
    """

    invalid_evidence = ResumeEvidence(
        evidence_id="EVID-999",
        resume_section="Experience",
        text="Led a team of ten senior engineers at a Fortune 500 company.",
        supported_requirement_ids=["REQ-001"],
        strength="strong",
        explanation="Claims leadership experience.",
    )

    return GapAnalysisResult(
        target_role_summary="Entry-level data analyst role focused on Python.",
        job_requirements=[
            JobRequirement(
                requirement_id="REQ-001",
                description="Experience with Python for data analysis.",
                priority="required",
                category="technical skill",
                keywords=["Python"],
            )
        ],
        matched_resume_evidence=[invalid_evidence],
        gaps=[],
        low_relevance_items=[],
        revision_brief=RevisionBrief(
            target_role_summary="Entry-level data analyst role focused on Python.",
            must_address_requirement_ids=["REQ-001"],
            keywords_to_include_if_truthful=[],
            gaps_to_address=[],
            resume_evidence_to_preserve=[invalid_evidence],
            low_relevance_items_to_reduce=[],
            instructions_for_revision_agent=[],
        ),
        overall_fit_summary="Claims strong fit.",
        estimated_fit_score=70,
    )


def test_runner_repairs_gap_analysis_then_passes(monkeypatch: Any) -> None:
    def fake_run_gap_analysis(
        job_description: str,
        current_resume: str,
        llm_client: Any = None,
    ) -> GapAnalysisResult:
        return _sample_invalid_gap_analysis_result()

    def fake_run_gap_analysis_repair(
        job_description: str,
        current_resume: str,
        previous_result: GapAnalysisResult,
        validation_errors: list[str],
        llm_client: Any = None,
    ) -> GapAnalysisResult:
        assert validation_errors
        return _sample_gap_analysis_result()

    def fake_run_resume_revision(
        current_resume: str,
        coursework_student_info: str,
        revision_brief: RevisionBrief,
        llm_client: Any = None,
    ) -> ResumeRevisionResult:
        return _sample_resume_revision_result()

    monkeypatch.setattr(
        "src.graph.nodes.run_gap_analysis",
        fake_run_gap_analysis,
    )
    monkeypatch.setattr(
        "src.graph.nodes.run_gap_analysis_repair",
        fake_run_gap_analysis_repair,
    )
    monkeypatch.setattr(
        "src.graph.nodes.run_resume_revision",
        fake_run_resume_revision,
    )

    result = run_resume_adjuster(
        job_description="Data analyst internship requiring Python and data analysis skills.",
        current_resume=(
            "Student resume with Python project. Built a Python project for "
            "analyzing student survey data."
        ),
        coursework_student_info="Completed Python coursework and data analysis project.",
    )

    assert result.success is True
    assert result.resume_revision is not None
    assert result.gap_analysis is not None
    assert result.gap_analysis.revision_brief.gap_analysis_confidence == 100
    assert any(
        step.step_name == "Gap Analysis Repair" for step in result.agent_trace
    )


def test_runner_proceeds_with_low_confidence_after_exhausting_repairs(
    monkeypatch: Any,
) -> None:
    repair_calls: list[Any] = []
    captured_revision_briefs: list[RevisionBrief] = []

    def fake_run_gap_analysis(
        job_description: str,
        current_resume: str,
        llm_client: Any = None,
    ) -> GapAnalysisResult:
        return _sample_invalid_gap_analysis_result()

    def fake_run_gap_analysis_repair(
        job_description: str,
        current_resume: str,
        previous_result: GapAnalysisResult,
        validation_errors: list[str],
        llm_client: Any = None,
    ) -> GapAnalysisResult:
        repair_calls.append(validation_errors)
        return _sample_invalid_gap_analysis_result()

    def fake_run_resume_revision(
        current_resume: str,
        coursework_student_info: str,
        revision_brief: RevisionBrief,
        llm_client: Any = None,
    ) -> ResumeRevisionResult:
        captured_revision_briefs.append(revision_brief)
        return _sample_resume_revision_result()

    monkeypatch.setattr(
        "src.graph.nodes.run_gap_analysis",
        fake_run_gap_analysis,
    )
    monkeypatch.setattr(
        "src.graph.nodes.run_gap_analysis_repair",
        fake_run_gap_analysis_repair,
    )
    monkeypatch.setattr(
        "src.graph.nodes.run_resume_revision",
        fake_run_resume_revision,
    )

    result = run_resume_adjuster(
        job_description="Data analyst internship requiring Python.",
        current_resume=(
            "Student resume with Python project. Built a Python project for "
            "analyzing student survey data."
        ),
        coursework_student_info="Completed Python coursework and data analysis project.",
    )

    # The workflow never halts on the semantic check: Agent 2 still runs.
    assert result.success is True
    assert result.resume_revision is not None
    assert len(repair_calls) == 3

    assert len(captured_revision_briefs) == 1
    forwarded_brief = captured_revision_briefs[0]
    assert forwarded_brief.gap_analysis_confidence < 100
    assert forwarded_brief.gap_analysis_semantic_warnings != []


def test_runner_repairs_resume_revision_then_passes(monkeypatch: Any) -> None:
    def fake_run_gap_analysis(
        job_description: str,
        current_resume: str,
        llm_client: Any = None,
    ) -> GapAnalysisResult:
        return _sample_gap_analysis_result()

    def fake_run_resume_revision(
        current_resume: str,
        coursework_student_info: str,
        revision_brief: RevisionBrief,
        llm_client: Any = None,
    ) -> ResumeRevisionResult:
        return _sample_invalid_resume_revision_result()

    def fake_run_resume_revision_repair(
        current_resume: str,
        coursework_student_info: str,
        revision_brief: RevisionBrief,
        previous_result: ResumeRevisionResult,
        validation_errors: list[str],
        llm_client: Any = None,
    ) -> ResumeRevisionResult:
        assert validation_errors
        return _sample_resume_revision_result()

    monkeypatch.setattr(
        "src.graph.nodes.run_gap_analysis",
        fake_run_gap_analysis,
    )
    monkeypatch.setattr(
        "src.graph.nodes.run_resume_revision",
        fake_run_resume_revision,
    )
    monkeypatch.setattr(
        "src.graph.nodes.run_resume_revision_repair",
        fake_run_resume_revision_repair,
    )

    result = run_resume_adjuster(
        job_description="Data analyst internship requiring Python and data analysis skills.",
        current_resume=(
            "Student resume with Python project. Built a Python project for "
            "analyzing student survey data."
        ),
        coursework_student_info="Completed Python coursework and data analysis project.",
    )

    assert result.success is True
    assert result.resume_revision is not None
    assert result.resume_revision.semantic_confidence == 100
    assert any(
        step.step_name == "Resume Revision Repair" for step in result.agent_trace
    )


def test_runner_finalizes_resume_revision_after_exhausting_repairs(
    monkeypatch: Any,
) -> None:
    repair_calls: list[Any] = []

    def fake_run_gap_analysis(
        job_description: str,
        current_resume: str,
        llm_client: Any = None,
    ) -> GapAnalysisResult:
        return _sample_gap_analysis_result()

    def fake_run_resume_revision(
        current_resume: str,
        coursework_student_info: str,
        revision_brief: RevisionBrief,
        llm_client: Any = None,
    ) -> ResumeRevisionResult:
        return _sample_invalid_resume_revision_result()

    def fake_run_resume_revision_repair(
        current_resume: str,
        coursework_student_info: str,
        revision_brief: RevisionBrief,
        previous_result: ResumeRevisionResult,
        validation_errors: list[str],
        llm_client: Any = None,
    ) -> ResumeRevisionResult:
        repair_calls.append(validation_errors)
        return _sample_invalid_resume_revision_result()

    monkeypatch.setattr(
        "src.graph.nodes.run_gap_analysis",
        fake_run_gap_analysis,
    )
    monkeypatch.setattr(
        "src.graph.nodes.run_resume_revision",
        fake_run_resume_revision,
    )
    monkeypatch.setattr(
        "src.graph.nodes.run_resume_revision_repair",
        fake_run_resume_revision_repair,
    )

    result = run_resume_adjuster(
        job_description="Data analyst internship requiring Python and data analysis skills.",
        current_resume=(
            "Student resume with Python project. Built a Python project for "
            "analyzing student survey data."
        ),
        coursework_student_info="Completed Python coursework and data analysis project.",
    )

    # The workflow never halts: the fabricated keyword is deterministically
    # stripped once repairs are exhausted, and the workflow still succeeds.
    assert result.success is True
    assert result.resume_revision is not None
    assert len(repair_calls) == 3
    assert "kubernetes" not in (result.final_resume_markdown or "").lower()
    assert result.resume_revision.semantic_confidence == 100
    assert result.resume_revision.semantic_warnings != []
    assert any(
        step.step_name == "Resume Revision Finalize" for step in result.agent_trace
    )