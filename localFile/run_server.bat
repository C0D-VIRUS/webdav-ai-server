@echo off
setlocal DisableDelayedExpansion

set "SCRIPT_DIR=%~dp0"
set "VENV_DIR=%SCRIPT_DIR%.venv"

echo Starting WebDAV + AI File Monitor ...
echo.

:: Check Python 3
python --version >nul 2>&1
if errorlevel 1 (
    echo Error: python not found. Please install Python 3.
    pause
    exit /b 1
)

:: Create venv if it doesn't exist
if not exist "%VENV_DIR%" (
    echo Creating virtual environment ...
    python -m venv "%VENV_DIR%"
)

:: Activate venv and install dependencies
call "%VENV_DIR%\Scripts\activate.bat"

echo Checking dependencies ...
python -m pip install --quiet --upgrade pip --no-cache-dir
python -m pip install --quiet google-genai watchdog --no-cache-dir

:: Run the server using the venv Python
python "%SCRIPT_DIR%server.py"

pause
