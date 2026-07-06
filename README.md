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

ResumeAdjuster uses exactly two agents.

### Agent 1: Job-Resume Gap Analyst

This agent reads the job description and the student's current resume.

Responsibilities:

- Extract job requirements
- Identify important job keywords
- Compare the resume against the job description
- Find missing or weakly supported qualifications
- Identify resume content that is less relevant to the target job
- Produce a structured revision brief for Agent 2

Agent 1 outputs a structured revision brief. This brief becomes the handoff between the two agents.

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

## Workflow

```text
Job Description + Current Resume
        ↓
Agent 1: Job-Resume Gap Analyst
        ↓
Structured Revision Brief
        ↓
Current Resume + Coursework/Student Info + Revision Brief
        ↓
Agent 2: Resume Revision Agent
        ↓
Updated Resume + Explanation of Changes

## Project Structure

ResumeAdjuster/
│
├── README.md
├── requirements.txt
├── .env.example
├── .gitignore
│
├── app.py
│
├── data/
│   ├── sample_resume.txt
│   ├── sample_job_description.txt
│   └── sample_coursework_and_student_info.txt
│
├── outputs/
│   └── .gitkeep
│
├── src/
│   ├── __init__.py
│   ├── config.py
│   ├── llm_client.py
│   ├── schemas.py
│   ├── document_loader.py
│   ├── text_cleaner.py
│   ├── resume_renderer.py
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
    ├── test_graph_state.py
    ├── test_graph_workflow.py
    └── test_resume_renderer.py


```markdown
## Environment Variables

This project uses a local `.env` file for API keys and model settings. The `.env` file should **not** be committed to GitHub.

Create your own `.env` file based on `.env.example`:

```text
OPENAI_API_KEY=your_api_key_here
OPENAI_MODEL=gpt-4.1-mini