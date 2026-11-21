@echo off
setlocal
cd /d "%~dp0"
set PYTHONPATH=%~dp0;%PYTHONPATH%
if exist "%~dp0.venv\Scripts\python.exe" (
    "%~dp0.venv\Scripts\python.exe" -m velum_forge.cli studio %*
) else (
    echo [Velum Forge] First-run setup: provisioning standalone Python 3.12 environment...
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1" -LaunchStudio
)
