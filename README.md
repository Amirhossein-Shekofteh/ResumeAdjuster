# ResumeAdjuster

ResumeAdjuster is a LangGraph-based demo application that adjusts a student's resume for a target job description using two agents.

The project is designed for a student-friendly Agentic AI demonstration. It shows how an AI system can move through a structured workflow instead of producing a single one-shot answer.

## Goal

The application reads:

- A job description
- A student's current resume
- The student's coursework and related background information

It then identifies gaps between the job description and the resume, checks whether the student's coursework or background can truthfully fill those gaps, and produces an updated resume tailored to the target role.

## Agent Design

ResumeAdjuster uses exactly two agents, each gated by an automated semantic checker and a review gate.

### Agent 1: Job-Resume Gap Analyst

This agent reads the job description and the student's current resume.

Responsibilities:

- Extract job requirements
- Identify important job keywords
- Compare the resume against the job description
- Find missing or weakly supported qualifications
- Identify resume content that is less relevant to the target job
- Produce a structured revision brief for Agent 2

Agent 1's output passes through a semantic checker (`gap_analysis_checker`), which can trigger an automatic repair pass if the brief fails validation. Once it passes (or repair attempts are exhausted), it moves through a review gate before being handed off to Agent 2.

### Agent 2: Resume Revision Agent

This agent does not re-read the full job description.

Instead, it reads:

- The student's current resume
- The student's coursework and related background information
- The structured revision brief from Agent 1

Responsibilities:

- Check whether coursework or student information can truthfully fill the resume gaps
- Add relevant information when supported by evidence
- Reduce or remove less relevant resume content
- Rewrite resume bullets for the target role
- Produce an updated resume
- Explain what changed and why

The system is designed to avoid inventing experience. Agent 2 can only use information from the original resume or the supplied coursework/student background information.

Agent 2's output passes through its own semantic checker (`resume_revision_checker`). On failure it can retry via a repair pass or fall through to a finalize step once repair attempts are exhausted. Its output then passes through a review gate — which screens for prompt injection, out-of-scope claims, and internal ID leaks — before the final output is produced.

## Workflow

```text
START
  ↓
clean_inputs
  ↓
gap_analysis (Agent 1)
  ↓
semantic_check ──(fail, attempts remain)──> gap_analysis_repair ──┐
  │                                                                 │
  │<────────────────────────────────────────────────────────────────┘
  ↓ (pass, or repairs exhausted)
agent1_review_gate
  ↓
resume_revision (Agent 2)
  ↓
resume_revision_semantic_check ──(fail, attempts remain)──> resume_revision_repair ──┐
  │                                                                                    │
  │<─────────────────────────────────────────────────────────────────────────────────┘
  ├──(fail, exhausted)──> resume_revision_finalize ──┐
  │                                                    │
  ↓ (pass)                                             ↓
agent2_review_gate <────────────────────────────────────
  ↓
final_output
  ↓
END
```

See [src/graph/builder.py](src/graph/builder.py) for the authoritative graph definition.

## Project Structure

```text
ResumeAdjuster/
│
├── README.md
├── WORKSHOP_PREREQUISITES.md
├── WORKSHOP_TASK.md
├── requirements.txt
├── pytest.ini
├── .env.example
├── .gitignore
│
├── app.py
│
├── data/
│   ├── sample_resume.txt
│   ├── sample_job_description.txt
│   ├── sample_coursework_and_student_info.txt
│   └── Instruction.md
│
├── outputs/
│   └── .gitkeep
│
├── scripts/
│   └── test_gemini.py
│
├── src/
│   ├── __init__.py
│   ├── config.py
│   ├── llm_client.py
│   ├── schemas.py
│   ├── document_loader.py
│   ├── text_cleaner.py
│   ├── resume_renderer.py
│   ├── scoring.py
│   │
│   ├── graph/
│   │   ├── __init__.py
│   │   ├── state.py
│   │   ├── nodes.py
│   │   ├── builder.py
│   │   └── runner.py
│   │
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── gap_analyst_agent.py
│   │   └── resume_revision_agent.py
│   │
│   ├── checks/
│   │   ├── __init__.py
│   │   ├── semantic_check_result.py
│   │   ├── gap_analysis_checker.py
│   │   ├── resume_revision_checker.py
│   │   └── review_gate.py
│   │
│   ├── prompts/
│   │   ├── gap_analysis_prompt.py
│   │   └── resume_revision_prompt.py
│   │
│   └── utils/
│       ├── __init__.py
│       ├── logging_utils.py
│       └── formatting.py
│
└── tests/
    ├── test_document_loader.py
    ├── test_text_cleaner.py
    ├── test_formatting.py
    ├── test_scoring.py
    ├── test_graph_state.py
    ├── test_graph_workflow.py
    ├── test_resume_renderer.py
    ├── test_gap_analyst_agent.py
    ├── test_gap_analysis_checker.py
    ├── test_resume_revision_agent.py
    ├── test_resume_revision_checker.py
    └── test_review_gate.py
```

## Environment Variables

This project uses a local `.env` file for API keys and model settings. The `.env` file should **not** be committed to GitHub.

Create your own `.env` file based on `.env.example`:

```text
LLM_PROVIDER=openai
OPENAI_API_KEY=your_api_key_here
OPENAI_MODEL=gpt-4.1-mini
GEMINI_API_KEY=your_api_key_here
GEMINI_MODEL=gemini-flash-lite-latest
MODEL_TEMPERATURE=0.2
MAX_INPUT_TEXT_LENGTH=20000
```