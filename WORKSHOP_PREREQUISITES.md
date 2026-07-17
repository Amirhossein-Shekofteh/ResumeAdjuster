# Workshop Prerequisites

One-time machine setup for the [WORKSHOP_TASK.md](WORKSHOP_TASK.md) exercise (adding an
"Updated Resume" tab with LaTeX preview + Word/PDF download). Do this **before** the
workshop starts so the task itself is pure coding.

1. **Python 3.12.** This project is built and tested against Python 3.12.6. Check what
   you have:
   ```
   python3 --version
   ```
   If you don't have Python 3.12, install it from https://www.python.org/downloads/ or
   via a version manager (e.g. `pyenv install 3.12`).

2. **Homebrew** (macOS only) — needed to install `pandoc` and `tectonic`, the two
   system-level tools this feature relies on for PDF/Word generation. Skip this if you
   already have Homebrew:
   ```
   /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
   ```
   *(Linux: install `pandoc` via your package manager, e.g. `apt install pandoc`, and
   `tectonic` per https://tectonic-typesetting.github.io/en-US/install.html. Windows:
   `choco install pandoc tectonic`, or see the same install pages.)*

3. **Install pandoc and tectonic**, then verify both are on `PATH`:
   ```
   brew install pandoc tectonic
   pandoc --version
   tectonic --version
   ```

4. **Create the virtual environment and install Python dependencies** (from inside the
   `ResumeAdjuster/` folder). Use `python3.12` explicitly rather than the bare `python3`
   — if you have more than one Python on `PATH` (common with pyenv, Homebrew, or a
   system install side-by-side), `python3` can silently resolve to a different version
   than the one you just verified in step 1:
   ```
   python3.12 -m venv .venv       # Windows: py -3.12 -m venv .venv
   source .venv/bin/activate      # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```
   This installs `pypandoc` along with everything else already in `requirements.txt` —
   but `pypandoc` is only a thin Python wrapper. It calls out to the real `pandoc`
   executable on your system `PATH` (installed in step 3); it does not install `pandoc`
   itself, which is why that has to happen first.

5. **`.env` file** — if you haven't already (per the main `README.md`), create a `.env`
   with the same keys as `.env.example` so `streamlit run app.py` can call the agents.
   Either copy the template and edit it in your editor:
   ```
   cp .env.example .env
   ```
   ...or write it directly from the shell, filling in real values as you go (replace
   the placeholders below — at minimum `OPENAI_API_KEY` or `GEMINI_API_KEY`, matching
   whichever `LLM_PROVIDER` you use):
   ```
   cat > .env <<'EOF'
   LLM_PROVIDER=openai
   OPENAI_API_KEY=your-openai-key-here
   OPENAI_MODEL=gpt-4.1-mini
   GEMINI_API_KEY=your-gemini-key-here
   GEMINI_MODEL=gemini-flash-lite-latest
   MODEL_TEMPERATURE=0.2
   MAX_INPUT_TEXT_LENGTH=20000
   EOF
   ```
   These keys must match `.env.example` — if that file changes, update the command
   above (or just use `cp` instead, which never goes out of sync).

`pandoc` and `tectonic` are OS-level binaries, not Python packages — that's why they
can't simply live in `requirements.txt` and get pulled in by `pip install`. Once steps
1–5 are done, you're ready to start [WORKSHOP_TASK.md](WORKSHOP_TASK.md).
