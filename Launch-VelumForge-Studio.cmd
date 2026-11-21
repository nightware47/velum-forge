@echo off
setlocal
cd /d "%~dp0"
set PYTHONPATH=%~dp0;%PYTHONPATH%
if exist "%~dp0.venv\Scripts\python.exe" (
    "%~dp0.venv\Scripts\python.exe" -m velum_forge.cli studio %*
) else (
    python -m velum_forge.cli studio %*
)
