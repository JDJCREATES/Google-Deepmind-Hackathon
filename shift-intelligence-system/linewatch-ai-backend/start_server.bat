@echo off
cd /d "%~dp0"
echo 🚀 Starting LineWatch AI Backend...
echo -----------------------------------
echo Using Virtual Environment: .venv\Scripts\python.exe
echo -----------------------------------

IF EXIST ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -m app.main
) ELSE (
    echo ❌ ERROR: Virtual environment not found in .venv
    echo Please run: python -m venv .venv
    echo And then: .venv\Scripts\pip install -e .
)

pause
