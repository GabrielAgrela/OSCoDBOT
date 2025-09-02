@echo off
setlocal ENABLEDELAYEDEXPANSION
title Call of the Dragons Bot

REM Change to the folder where this script lives
cd /d "%~dp0"

REM Activate local virtual environment if present
if exist ".venv\Scripts\activate.bat" (
  call ".venv\Scripts\activate.bat"
)

REM If a GUI Python exists, launch it detached so no CMD window remains
if exist ".venv\Scripts\pythonw.exe" (
  start "" /min ".venv\Scripts\pythonw.exe" main.py
  goto :end
)

where pythonw >NUL 2>&1
if %ERRORLEVEL%==0 (
  start "" /min pythonw main.py
  goto :end
)

where pyw >NUL 2>&1
if %ERRORLEVEL%==0 (
  start "" /min pyw main.py
  goto :end
)

REM Fallbacks (console will be visible in these cases)
where py >NUL 2>&1
if %ERRORLEVEL%==0 (
  py main.py
) else (
  python main.py
)

:end
endlocal
