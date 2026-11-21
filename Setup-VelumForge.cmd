@echo off
setlocal
cd /d "%~dp0"
set PYTHONPATH=%~dp0;%PYTHONPATH%
if exist "%~dp0.venv\Scripts\pythonw.exe" (
    start "" "%~dp0.venv\Scripts\pythonw.exe" -m velum_forge.cli setup-gui
) else (
    python -m velum_forge.cli setup-gui
)
