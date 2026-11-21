<#
.SYNOPSIS
Velum Forge 1-Click Windows Installer & AI Workflow Bootstrapper.

.DESCRIPTION
Works both locally (`.\install.ps1`) and remotely (`irm https://raw.githubusercontent.com/velumix/velum-forge/main/install.ps1 | iex`):
  1. Clones `velumix/velum-forge` if run remotely.
  2. Creates/updates `.venv` (Python 3.12 via `uv` or `python -m venv`) with `build123d`, `trimesh`, `pymeshlab`, `pillow`, `numpy`.
  3. Installs the official Antigravity Plugin (`~/.gemini/config/plugins/velum-forge`) and Claude Code skills (`~/.claude/skills/velum-*`).
  4. Adds the `vforge` CLI shim to `~/.local/bin` (and User PATH if missing).
  5. Creates a Desktop shortcut for Velum Forge Studio.
#>
[CmdletBinding()]
param(
    [string]$InstallDir = "",
    [string]$Workspace = "",
    [switch]$Gui,
    [switch]$LaunchStudio,
    [switch]$SkipVenv
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# Determine repository root (clone if invoked via `irm ... | iex`)
if ($PSScriptRoot -and (Test-Path (Join-Path $PSScriptRoot "pyproject.toml"))) {
    $RepoRoot = (Resolve-Path $PSScriptRoot).Path
} else {
    if ([string]::IsNullOrWhiteSpace($InstallDir)) {
        $InstallDir = Join-Path $HOME "VelumForge"
    }
    if (-not (Test-Path (Join-Path $InstallDir ".git"))) {
        Write-Host "[Velum Forge] Cloning https://github.com/velumix/velum-forge.git -> $InstallDir ..." -ForegroundColor Cyan
        git clone https://github.com/velumix/velum-forge.git $InstallDir
    } else {
        Write-Host "[Velum Forge] Updating existing clone at $InstallDir ..." -ForegroundColor Cyan
        git -C $InstallDir pull --ff-only
    }
    $RepoRoot = (Resolve-Path $InstallDir).Path
}

if ($Gui) {
    $sysPy = (Get-Command python -ErrorAction Stop).Source
    $env:PYTHONPATH = "$RepoRoot;$env:PYTHONPATH"
    & $sysPy -m velum_forge.cli setup-gui
    exit $LASTEXITCODE
}

Write-Host "`n=== Velum Forge 1.0 Installer ===" -ForegroundColor Cyan
Write-Host "Repository: $RepoRoot"

$VenvDir = Join-Path $RepoRoot ".venv"
$VenvPy = Join-Path $VenvDir "Scripts\python.exe"

if (-not $SkipVenv) {
    $uvCmd = Get-Command uv -ErrorAction SilentlyContinue
    if ($uvCmd) {
        Write-Host "[1/4] Provisioning Python 3.12 CAD environment via uv..." -ForegroundColor Cyan
        & $uvCmd.Source venv $VenvDir --python 3.12 --allow-existing
        & $uvCmd.Source pip install --python $VenvPy -e $RepoRoot
    } else {
        Write-Host "[1/4] Provisioning Python CAD environment via venv + pip..." -ForegroundColor Cyan
        if (-not (Test-Path $VenvPy)) {
            python -m venv $VenvDir
        }
        & $VenvPy -m pip install --upgrade pip
        & $VenvPy -m pip install -e $RepoRoot
    }
}

$RunPy = if (Test-Path $VenvPy) { $VenvPy } else { (Get-Command python).Source }
$env:PYTHONPATH = "$RepoRoot;$env:PYTHONPATH"

Write-Host "[2/4] Installing AI Agent Plugins & Skills (Antigravity + Claude Code)..." -ForegroundColor Cyan
$aiArgs = @("-m", "velum_forge.cli", "install-ai")
if (-not [string]::IsNullOrWhiteSpace($Workspace)) {
    $aiArgs += @("--workspace", $Workspace)
}
& $RunPy @aiArgs

Write-Host "[3/4] Installing 'vforge' CLI shim & User PATH..." -ForegroundColor Cyan
$BinDir = Join-Path $HOME ".local\bin"
New-Item -ItemType Directory -Force -Path $BinDir | Out-Null
$ShimPath = Join-Path $BinDir "vforge.cmd"
"@echo off`r`nset PYTHONPATH=$RepoRoot;%PYTHONPATH%`r`n`"$RunPy`" -m velum_forge.cli %*`r`n" | Set-Content -Path $ShimPath -Encoding ASCII

$UserPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($UserPath -notlike "*$BinDir*") {
    [Environment]::SetEnvironmentVariable("Path", "$BinDir;$UserPath", "User")
    $env:Path = "$BinDir;$env:Path"
    Write-Host "  Added $BinDir to User PATH." -ForegroundColor Green
}

Write-Host "[4/4] Creating Desktop Shortcut & Running Environment Doctor..." -ForegroundColor Cyan
try {
    $DeskDir = if (Test-Path (Join-Path $HOME "OneDrive\Desktop")) { Join-Path $HOME "OneDrive\Desktop" } else { Join-Path $HOME "Desktop" }
    $WshShell = New-Object -ComObject WScript.Shell
    $Shortcut = $WshShell.CreateShortcut((Join-Path $DeskDir "Velum Forge Studio.lnk"))
    $Shortcut.TargetPath = (Join-Path $RepoRoot "Launch-VelumForge-Studio.cmd")
    $Shortcut.WorkingDirectory = $RepoRoot
    $Shortcut.Description = "Launch Velum Forge 3D CAD, PBR & QA Studio"
    $Shortcut.Save()
} catch {
    Write-Host "  (Skipped desktop shortcut creation: $_)" -ForegroundColor DarkGray
}

& $RunPy -m velum_forge.cli doctor

Write-Host "`n[DONE] Run 'vforge studio' or double-click 'Launch-VelumForge-Studio.cmd' anytime!" -ForegroundColor Green
if ($LaunchStudio) {
    Start-Process -FilePath (Join-Path $RepoRoot "Launch-VelumForge-Studio.cmd") -WorkingDirectory $RepoRoot
}
