# ResumeAdjuster
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