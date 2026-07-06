from __future__ import annotations

from src.graph.state import build_initial_state


def test_initial_state_can_be_created() -> None:
    state = build_initial_state(
        job_description="Data analyst internship requiring Python.",
        current_resume="Student resume with Python project.",
        coursework_student_info="Completed data analysis coursework.",
    )

    assert state["job_description"] == "Data analyst internship requiring Python."
    assert state["current_resume"] == "Student resume with Python project."
    assert state["coursework_student_info"] == "Completed data analysis coursework."


def test_initial_state_has_required_default_keys() -> None:
    state = build_initial_state(
        job_description="Job description",
        current_resume="Resume",
        coursework_student_info="Coursework",
    )

    assert "gap_analysis" in state
    assert "revision_brief" in state
    assert "resume_revision" in state
    assert "final_resume_markdown" in state
    assert "final_output" in state
    assert "errors" in state
    assert "agent_trace" in state


def test_initial_state_defaults_work() -> None:
    state = build_initial_state(
        job_description="Job description",
        current_resume="Resume",
        coursework_student_info="Coursework",
    )

    assert state["gap_analysis"] is None
    assert state["revision_brief"] is None
    assert state["resume_revision"] is None
    assert state["final_resume_markdown"] is None
    assert state["final_output"] is None
    assert state["errors"] == []
    assert state["agent_trace"] == []