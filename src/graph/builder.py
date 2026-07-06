from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph

from src.graph.nodes import (
    clean_inputs_node,
    final_output_node,
    gap_analysis_node,
    resume_revision_node,
)
from src.graph.state import ResumeAdjusterState


def build_resume_adjuster_graph() -> Any:
    """
    Build and compile the ResumeAdjuster LangGraph workflow.

    Workflow:

    START
      ↓
    clean_inputs_node
      ↓
    gap_analysis_node
      ↓
    resume_revision_node
      ↓
    final_output_node
      ↓
    END
    """

    graph = StateGraph(ResumeAdjusterState)

    graph.add_node("clean_inputs", clean_inputs_node)
    graph.add_node("gap_analysis", gap_analysis_node)
    graph.add_node("resume_revision", resume_revision_node)
    graph.add_node("final_output", final_output_node)

    graph.add_edge(START, "clean_inputs")
    graph.add_edge("clean_inputs", "gap_analysis")
    graph.add_edge("gap_analysis", "resume_revision")
    graph.add_edge("resume_revision", "final_output")
    graph.add_edge("final_output", END)

    return graph.compile()