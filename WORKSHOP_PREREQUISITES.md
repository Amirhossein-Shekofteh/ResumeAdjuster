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
   `ResumeAdjuster/` folder):
   ```
   python3 -m venv .venv
   source .venv/bin/activate      # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```
   This installs `pypandoc` along with everything else already in `requirements.txt` —
   but `pypandoc` is only a thin Python wrapper. It calls out to the real `pandoc`
   executable on your system `PATH` (installed in step 3); it does not install `pandoc`
   itself, which is why that has to happen first.

5. **`.env` file** — if you haven't already (per the main `README.md`), copy
   `.env.example` to `.env` and add your LLM API key so `streamlit run app.py` can call
   the agents.

`pandoc` and `tectonic` are OS-level binaries, not Python packages — that's why they
can't simply live in `requirements.txt` and get pulled in by `pip install`. Once steps
1–5 are done, you're ready to start [WORKSHOP_TASK.md](WORKSHOP_TASK.md).
