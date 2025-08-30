@echo off
setlocal ENABLEDELAYEDEXPANSION
title Call of the Dragons Bot

REM Change to the folder where this script lives
cd /d "%~dp0"

REM Activate local virtual environment if present
if exist ".venv\Scripts\activate.bat" (
  call ".venv\Scripts\activate.bat"
)

REM Prefer the Python launcher if available
where py >NUL 2>&1
if %ERRORLEVEL%==0 (
  py main.py
) else (
  python main.py
)

endlocal
