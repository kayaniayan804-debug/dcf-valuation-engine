@echo off
REM One-click launcher: creates a private venv, installs deps, opens the app.
cd /d "%~dp0"

REM Skip Streamlit's first-run email prompt (it blocks the launch)
if not exist "%USERPROFILE%\.streamlit" mkdir "%USERPROFILE%\.streamlit"
if not exist "%USERPROFILE%\.streamlit\credentials.toml" (
    echo [general]> "%USERPROFILE%\.streamlit\credentials.toml"
    echo email = "">> "%USERPROFILE%\.streamlit\credentials.toml"
)

if not exist ".venv\Scripts\python.exe" (
    echo [1/3] Creating virtual environment - first run only...
    py -3.12 -m venv .venv 2>nul || py -3 -m venv .venv 2>nul || python -m venv .venv
)
echo [2/3] Installing dependencies - fast if already installed...
".venv\Scripts\python.exe" -m pip install --quiet --upgrade pip
".venv\Scripts\python.exe" -m pip install --quiet -r requirements.txt
if errorlevel 1 (
    echo Dependency install failed - see messages above.
    pause
    exit /b 1
)
echo [3/3] Launching app - your browser will open...
".venv\Scripts\python.exe" -m streamlit run app.py
pause
