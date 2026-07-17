# Workshop Prerequisites

One-time machine setup for the [WORKSHOP_TASK.md](WORKSHOP_TASK.md) exercise (adding an
"Updated Resume" tab with LaTeX preview + Word/PDF download). Do this **before** the
workshop starts so the task itself is pure coding.

Steps below are written for macOS, Linux, and Windows. Pick the block for your OS
wherever they diverge.

1. **Python 3.12.** This project is built and tested against Python 3.12.6. Check what
   you have:

   - macOS / Linux:
     ```
     python3 --version
     ```
   - Windows (PowerShell or Command Prompt):
     ```
     python --version
     ```
     (or `py -3.12 --version` if you use the `py` launcher with multiple Python
     versions installed)

   If you don't have Python 3.12, install it from https://www.python.org/downloads/,
   or via a version manager (`pyenv install 3.12` on macOS/Linux, `pyenv-win` or the
   `py` launcher on Windows).

2. **Package manager** — needed to install `pandoc` and `tectonic`, the two
   system-level tools this feature relies on for PDF/Word generation.

   - macOS: install Homebrew if you don't already have it:
     ```
     /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
     ```
   - Linux: use your distro's package manager (e.g. `apt`) — already installed.
   - Windows: use `winget`, which ships built in on Windows 10/11. Confirm it's
     available:
     ```
     winget --version
     ```
     If that fails, install "App Installer" from the Microsoft Store, then retry.

3. **Install pandoc and tectonic**, then verify both are on `PATH`.

   - macOS:
     ```
     brew install pandoc tectonic
     ```
   - Linux:
     ```
     sudo apt install pandoc
     curl --proto '=https' --tlsv1.2 -fsSL https://drop-sh.fullyjustified.net | sh
     ```
     This installs `tectonic` into `~/.local/bin` — make sure that directory is on
     your `PATH`. If you're not on an `apt`-based distro, see
     https://tectonic-typesetting.github.io/en-US/install.html for your package
     manager.
   - Windows (PowerShell):
     ```powershell
     # Install Pandoc
     winget install --source winget --exact --id JohnMacFarlane.Pandoc

     # Install Tectonic
     $tectonicDir = "$env:LOCALAPPDATA\Programs\Tectonic"
     New-Item -ItemType Directory -Force -Path $tectonicDir | Out-Null

     Push-Location $tectonicDir

     [System.Net.ServicePointManager]::SecurityProtocol =
         [System.Net.ServicePointManager]::SecurityProtocol -bor 3072

     Invoke-Expression (
         (New-Object System.Net.WebClient).DownloadString(
             "https://drop-ps1.fullyjustified.net"
         )
     )

     Pop-Location

     # Add Tectonic to the user's PATH
     $userPath = [Environment]::GetEnvironmentVariable("Path", "User")

     if (($userPath -split ";") -notcontains $tectonicDir) {
         [Environment]::SetEnvironmentVariable(
             "Path",
             "$userPath;$tectonicDir",
             "User"
         )
     }

     # Make it available in the current terminal immediately
     $env:Path += ";$tectonicDir"
     ```
     Open a new terminal window afterward so both the `winget`-installed `pandoc` and
     the updated `PATH` for `tectonic` take effect.

   Then verify both, from a new terminal window:
   ```
   pandoc --version
   tectonic --version
   ```

4. **Create the virtual environment and install Python dependencies** (from inside the
   `ResumeAdjuster/` folder). Use the pinned `3.12` interpreter explicitly rather than
   a bare `python`/`python3` — if you have more than one Python on `PATH` (common with
   pyenv, Homebrew, or a system install side-by-side), the unpinned command can
   silently resolve to a different version than the one you just verified in step 1:

   - macOS / Linux:
     ```
     python3.12 -m venv .venv
     source .venv/bin/activate
     pip install -r requirements.txt
     ```
   - Windows (PowerShell):
     ```powershell
     py -3.12 -m venv .venv
     .venv\Scripts\Activate.ps1
     pip install -r requirements.txt
     ```
     (Command Prompt instead of PowerShell: activate with `.venv\Scripts\activate.bat`)

   This installs `pypandoc` along with everything else already in `requirements.txt` —
   but `pypandoc` is only a thin Python wrapper. It calls out to the real `pandoc`
   executable on your system `PATH` (installed in step 3); it does not install `pandoc`
   itself, which is why that has to happen first.

5. **Get a Google AI Studio (Gemini) API key** (skip this if you're using
   `LLM_PROVIDER=openai` with your own OpenAI key instead):
   - Go to https://aistudio.google.com/apikey and sign in.
   - Click **Create API Key** → **Create API key in new project**.
   - Copy the key and save it — you'll paste it into `GEMINI_API_KEY` in your `.env`
     file (step 6 below), not into any external tool.
   - Create it the day before the workshop (not weeks ahead), and keep it private —
     don't commit it or share it in chat.

6. **`.env` file** — if you haven't already (per the main `README.md`), create a `.env`
   with the same keys as `.env.example` so `streamlit run app.py` can call the agents.

   Either copy the template and edit it in your editor:

   - macOS / Linux:
     ```
     cp .env.example .env
     ```
   - Windows (PowerShell):
     ```powershell
     Copy-Item .env.example .env
     ```

   ...or write it directly from the terminal, filling in real values as you go
   (replace the placeholders below — at minimum `OPENAI_API_KEY` or
   `GEMINI_API_KEY`, matching whichever `LLM_PROVIDER` you use):

   - macOS / Linux:
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
   - Windows (PowerShell):
     ```powershell
     @"
     LLM_PROVIDER=openai
     OPENAI_API_KEY=your-openai-key-here
     OPENAI_MODEL=gpt-4.1-mini
     GEMINI_API_KEY=your-gemini-key-here
     GEMINI_MODEL=gemini-flash-lite-latest
     MODEL_TEMPERATURE=0.2
     MAX_INPUT_TEXT_LENGTH=20000
     "@ | Set-Content -Path .env -Encoding utf8
     ```

   These keys must match `.env.example` — if that file changes, update the command
   above (or just use the copy command instead, which never goes out of sync).

`pandoc` and `tectonic` are OS-level binaries, not Python packages — that's why they
can't simply live in `requirements.txt` and get pulled in by `pip install`. Once steps
1–6 are done, you're ready to start [WORKSHOP_TASK.md](WORKSHOP_TASK.md).
