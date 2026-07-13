from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph

from src.graph.nodes import (
    clean_inputs_node,
    final_output_node,
    gap_analysis_node,
    gap_analysis_repair_node,
    resume_revision_finalize_node,
    resume_revision_node,
    resume_revision_repair_node,
    resume_revision_semantic_check_node,
    route_after_resume_revision_semantic_check,
    route_after_semantic_check,
    semantic_check_node,
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
    semantic_check_node --(pass, or repairs exhausted)--> resume_revision_node
      ↑                --(fail, attempts remain)-->  gap_analysis_repair_node
      └──────────────────────────────────────────────────┘
      ↓
    resume_revision_node
      ↓
    resume_revision_semantic_check_node --(pass)--> final_output_node
      ↑                                --(fail, attempts remain)--> resume_revision_repair_node
      ↑                                --(fail, exhausted)--> resume_revision_finalize_node
      └────────────────────────────────────────────────────────────┘
                                                                       ↓
                                                              resume_revision_finalize_node
                                                                       ↓
                                                                 final_output_node
      ↓
    END
    """

    graph = StateGraph(ResumeAdjusterState)

    graph.add_node("clean_inputs", clean_inputs_node)
    graph.add_node("gap_analysis", gap_analysis_node)
    graph.add_node("semantic_check", semantic_check_node)
    graph.add_node("gap_analysis_repair", gap_analysis_repair_node)
    graph.add_node("resume_revision", resume_revision_node)
    graph.add_node("resume_revision_semantic_check", resume_revision_semantic_check_node)
    graph.add_node("resume_revision_repair", resume_revision_repair_node)
    graph.add_node("resume_revision_finalize", resume_revision_finalize_node)
    graph.add_node("final_output", final_output_node)

    graph.add_edge(START, "clean_inputs")
    graph.add_edge("clean_inputs", "gap_analysis")
    graph.add_edge("gap_analysis", "semantic_check")
    graph.add_conditional_edges(
        "semantic_check",
        route_after_semantic_check,
        {
            "resume_revision": "resume_revision",
            "gap_analysis_repair": "gap_analysis_repair",
        },
    )
    graph.add_edge("gap_analysis_repair", "semantic_check")
    graph.add_edge("resume_revision", "resume_revision_semantic_check")
    graph.add_conditional_edges(
        "resume_revision_semantic_check",
        route_after_resume_revision_semantic_check,
        {
            "final_output": "final_output",
            "resume_revision_repair": "resume_revision_repair",
            "resume_revision_finalize": "resume_revision_finalize",
        },
    )
    graph.add_edge("resume_revision_repair", "resume_revision_semantic_check")
    graph.add_edge("resume_revision_finalize", "final_output")
    graph.add_edge("final_output", END)

    return graph.compile()