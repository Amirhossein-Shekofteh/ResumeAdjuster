# Instructions: Add Score Change Review Node

## Overview

The workflow currently has 4 nodes:

```
START → clean_inputs → gap_analysis → resume_revision → final_output → END
```

These instructions add a new **Node 4 — `score_change_review`** between `resume_revision` and `final_output`, making it a 5-step workflow:

```
START → clean_inputs → gap_analysis → resume_revision → score_change_review → final_output → END
```

This new node reruns gap analysis on the revised resume to measure whether Agent 2's changes improved the fit score, and surfaces the comparison in the UI as a new "Score Review" tab.

---

## Step 1 — `src/schemas.py`

### 1a. Add `ScoreChangeDecision` and `ScoreChangeReviewResult`

Place these **after** the `ResumeRevisionResult` class:

```python
ScoreChangeDecision = Literal["improved", "unchanged", "decreased"]


class ScoreChangeReviewResult(BaseModel):
    """
    Reviewer output comparing the original resume score with the revised resume score.
    """

    initial_fit_score: int = Field(
        ge=0,
        le=100,
        description="Fit score for the original resume."
    )
    revised_fit_score: int = Field(
        ge=0,
        le=100,
        description="Fit score for the revised resume."
    )
    score_delta: int = Field(
        ge=-100,
        le=100,
        description="Difference between revised_fit_score and initial_fit_score."
    )
    decision: ScoreChangeDecision = Field(
        description="Whether the revised resume improved, stayed unchanged, or decreased."
    )
    summary: str = Field(
        description="Plain-language explanation of how the suggestions affected the score."
    )
```

### 1b. Update `FinalWorkflowResult`

Add one field after `resume_revision` inside `FinalWorkflowResult`:

```python
score_review: ScoreChangeReviewResult | None = Field(
    default=None,
    description="Reviewer result comparing initial and revised resume fit scores."
)
```

---

## Step 2 — `src/graph/state.py`

### 2a. Update the import

Add `ScoreChangeReviewResult` to the existing `from src.schemas import (...)` block:

```python
from src.schemas import (
    AgentTraceStep,
    FinalWorkflowResult,
    GapAnalysisResult,
    ResumeRevisionResult,
    RevisionBrief,
    ScoreChangeReviewResult,
)
```

### 2b. Add two fields to `ResumeAdjusterState`

Insert after `resume_revision`:

```python
revised_gap_analysis: GapAnalysisResult | None
score_review: ScoreChangeReviewResult | None
```

### 2c. Update `build_initial_state()`

Add two `None` entries to the returned dict, after `"resume_revision": None`:

```python
"revised_gap_analysis": None,
"score_review": None,
```

The full returned dict should look like:

```python
return {
    "job_description": job_description,
    "current_resume": current_resume,
    "coursework_student_info": coursework_student_info,
    "gap_analysis": None,
    "revision_brief": None,
    "resume_revision": None,
    "revised_gap_analysis": None,
    "score_review": None,
    "final_resume_markdown": None,
    "final_output": None,
    "errors": [],
    "agent_trace": [],
}
```

---

## Step 3 — `src/graph/nodes.py`

### 3a. Update the import

Add `ScoreChangeReviewResult` to the existing `from src.schemas import ...` line:

```python
from src.schemas import AgentTraceStep, FinalWorkflowResult, ScoreChangeReviewResult
```

> `run_gap_analysis` is already imported at the top of this file — no additional import needed.

### 3b. Add `score_change_review_node()`

Insert this function **after** `resume_revision_node()` and **before** `final_output_node()`:

```python
def score_change_review_node(state: ResumeAdjusterState) -> dict[str, Any]:
    """
    Node 4: Review whether Agent 2's resume revision improved the fit score.

    This node reuses Agent 1's scoring behavior by running gap analysis again,
    but this time on the revised resume produced by Agent 2.
    """

    if _has_errors(state):
        trace = _trace_step(
            step_number=4,
            step_name="Score Change Review",
            agent_name="Score Change Reviewer",
            status="warning",
            input_summary="Skipped because previous workflow errors exist.",
            output_summary="Score change review was not run.",
        )

        return {"agent_trace": [trace]}

    try:
        initial_gap_analysis = state.get("gap_analysis")
        resume_revision = state.get("resume_revision")

        if initial_gap_analysis is None:
            raise ValueError("Missing gap_analysis from Agent 1.")

        if resume_revision is None:
            raise ValueError("Missing resume_revision from Agent 2.")

        cleaned_job_description = _required_text(state, "cleaned_job_description")
        revised_resume = resume_revision.updated_resume_markdown.strip()

        if not revised_resume:
            raise ValueError("Missing updated resume markdown from Agent 2.")

        revised_gap_analysis = run_gap_analysis(
            job_description=cleaned_job_description,
            current_resume=revised_resume,
        )

        initial_score = initial_gap_analysis.estimated_fit_score
        revised_score = revised_gap_analysis.estimated_fit_score
        score_delta = revised_score - initial_score

        if score_delta > 0:
            decision = "improved"
            summary = (
                f"The revised resume improved the estimated fit score "
                f"from {initial_score}/100 to {revised_score}/100 "
                f"for a gain of {score_delta} points."
            )
        elif score_delta == 0:
            decision = "unchanged"
            summary = (
                f"The revised resume kept the same estimated fit score: "
                f"{initial_score}/100."
            )
        else:
            decision = "decreased"
            summary = (
                f"The revised resume decreased the estimated fit score "
                f"from {initial_score}/100 to {revised_score}/100 "
                f"for a change of {score_delta} points."
            )

        score_review = ScoreChangeReviewResult(
            initial_fit_score=initial_score,
            revised_fit_score=revised_score,
            score_delta=score_delta,
            decision=decision,
            summary=summary,
        )

        trace = _trace_step(
            step_number=4,
            step_name="Score Change Review",
            agent_name="Score Change Reviewer",
            status="success",
            input_summary="Agent 1 initial score and Agent 2 revised resume.",
            output_summary=summary,
            metadata={
                "initial_fit_score": initial_score,
                "revised_fit_score": revised_score,
                "score_delta": score_delta,
                "decision": decision,
            },
        )

        return {
            "revised_gap_analysis": revised_gap_analysis,
            "score_review": score_review,
            "agent_trace": [trace],
        }

    except Exception as exc:
        error_message = f"Score change review failed: {exc}"

        trace = _trace_step(
            step_number=4,
            step_name="Score Change Review",
            agent_name="Score Change Reviewer",
            status="error",
            input_summary="Agent 1 initial score and Agent 2 revised resume.",
            output_summary=error_message,
        )

        return {
            "errors": [error_message],
            "agent_trace": [trace],
        }
```

### 3c. Update `final_output_node()`

**Add** this line alongside the existing `state.get(...)` reads at the top of the function:

```python
score_review = state.get("score_review")
```

**Pass it** into `FinalWorkflowResult(...)`:

```python
final_output = FinalWorkflowResult(
    success=success,
    gap_analysis=gap_analysis,
    resume_revision=resume_revision,
    score_review=score_review,
    final_resume_markdown=final_resume_markdown,
    agent_trace=final_trace,
    errors=all_errors,
)
```

**Change the step number** in the `_trace_step(...)` call from `4` to `5`:

```python
trace = _trace_step(
    step_number=5,
    step_name="Build Final Output",
    ...
)
```

---

## Step 4 — `src/graph/builder.py`

### 4a. Update the import

Add `score_change_review_node` to the existing `from src.graph.nodes import (...)` block:

```python
from src.graph.nodes import (
    clean_inputs_node,
    final_output_node,
    gap_analysis_node,
    resume_revision_node,
    score_change_review_node,
)
```

### 4b. Register the node

Add this line after `graph.add_node("resume_revision", resume_revision_node)`:

```python
graph.add_node("score_change_review", score_change_review_node)
```

### 4c. Rewire the edges

Replace:

```python
graph.add_edge("resume_revision", "final_output")
```

With:

```python
graph.add_edge("resume_revision", "score_change_review")
graph.add_edge("score_change_review", "final_output")
```

### 4d. Update the docstring

Update the workflow diagram in the `build_resume_adjuster_graph()` docstring to show the new 5-step flow:

```
START
  ↓
clean_inputs_node
  ↓
gap_analysis_node
  ↓
resume_revision_node
  ↓
score_change_review_node
  ↓
final_output_node
  ↓
END
```

---

## Step 5 — `app.py`

### 5a. Add `_render_score_review_output()`

Insert this function after `_render_agent_2_output()`:

```python
def _render_score_review_output(final_result) -> None:
    """
    Display reviewer output comparing initial and revised scores.
    """

    st.subheader("Reviewer Output: Score Change Review")

    score_review = getattr(final_result, "score_review", None)

    if score_review is None:
        st.info("No score change review was generated.")
        return

    col1, col2, col3 = st.columns(3)
    col1.metric("Initial Fit", f"{score_review.initial_fit_score}/100")
    col2.metric("Revised Fit", f"{score_review.revised_fit_score}/100")
    col3.metric("Score Change", f"{score_review.score_delta:+d}")

    st.markdown(f"**Decision:** `{score_review.decision}`")
    st.write(score_review.summary)
```

### 5b. Update the tabs

The current code has **5 tabs** (`tab1`–`tab5`). Replace the entire `st.tabs(...)` call with **6 tabs**, inserting "Score Review" at position 3:

**Before:**
```python
tab1, tab2, tab3, tab4, tab5 = st.tabs(
    [
        "Agent 1: Gap Analysis",
        "Agent 2: Resume Revision",
        "Updated Resume",
        "Workflow Trace",
        "Full Report",
    ]
)
```

**After:**
```python
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(
    [
        "Agent 1: Gap Analysis",
        "Agent 2: Resume Revision",
        "Score Review",
        "Updated Resume",
        "Workflow Trace",
        "Full Report",
    ]
)
```

Then update the `with tabN:` blocks to match the new numbering:

```python
with tab1:
    _render_agent_1_output(final_result)

with tab2:
    _render_agent_2_output(final_result)

with tab3:
    _render_score_review_output(final_result)

with tab4:
    _render_updated_resume(final_result)

with tab5:
    _render_workflow_trace(final_result)

with tab6:
    st.markdown(render_final_report(final_result))
    _render_full_report_download(final_result)
```

### 5c. Update the sidebar workflow description

Find the sidebar markdown block and add step 4:

```python
st.sidebar.markdown(
    """
    **Workflow**

    1. Clean inputs  
    2. Agent 1 analyzes job-resume gaps  
    3. Agent 2 revises the resume  
    4. Score change review  
    5. Final report is generated
    """
)
```

---

## Verification

1. Run `streamlit run app.py` and load the sample data.
2. Click **Run two-agent resume adjustment**.
3. Confirm a "Score Review" tab appears showing three metrics: Initial Fit, Revised Fit, Score Change.
4. Open the **Workflow Trace** tab and confirm it shows 5 steps (1–5), with step 4 named "Score Change Review".
5. Test the error path: submit with a blank resume field and confirm the node emits a `warning` trace without crashing.
