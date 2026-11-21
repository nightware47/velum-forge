<#
.SYNOPSIS
Velum Forge Zero-Prerequisite Windows Installer & Native Dark-Mode Setup Wizard.

.DESCRIPTION
Works on ANY Windows 10/11 PC — even if Python, uv, Git, and Blender are NOT on PATH (or if Python/Git are not installed at all!):
  1. Clones `velumix/velum-forge` via Git (or downloads GitHub release .zip if Git is not installed).
  2. Auto-discovers non-PATH Python installations (py.exe, AppData\Local\Programs\Python, Registry) AND/OR
     auto-downloads standalone `uv.exe` + portable CPython 3.12 automatically (zero admin rights needed!).
  3. Deep-scans for `blender.exe` across all drives, Steam libraries (`libraryfolders.vdf`), Registry (`App Paths`,
     `.blend` file associations, `Uninstall` keys, `MuiCache`), Blender Launcher, Scoop, Chocolatey & MS Store,
     and persists the verified path to `~/.velum-forge/config.json`.
  4. Provisions `.venv` (`build123d`, `trimesh`, `pymeshlab`, `pillow`, `numpy`), installs Antigravity + Claude skills,
     adds `vforge` to User PATH, and creates the Desktop Studio shortcut.
#>
[CmdletBinding()]
param(
    [string]$InstallDir = "",
    [string]$Workspace = "",
    [string]$BlenderPath = "",
    [switch]$Gui,
    [switch]$LaunchStudio,
    [switch]$SkipVenv
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

function Get-RegValue {
    param([string]$Path, [string]$Name = "")
    try {
        if (-not (Test-Path -LiteralPath $Path)) { return $null }
        if ([string]::IsNullOrEmpty($Name)) {
            $item = Get-Item -LiteralPath $Path -ErrorAction SilentlyContinue
            if ($item) { return $item.GetValue("") }
            return $null
        }
        return Get-ItemPropertyValue -LiteralPath $Path -Name $Name -ErrorAction SilentlyContinue
    } catch {
        return $null
    }
}

# ---------------------------------------------------------------------------
# Helper: Test Real Working Python (Rejects Fake Microsoft Store Stub!)
# ---------------------------------------------------------------------------
function Test-RealPython {
    param([string]$ExePath)
    if ([string]::IsNullOrWhiteSpace($ExePath) -or -not (Test-Path -LiteralPath $ExePath)) { return $false }
    try {
        $out = & $ExePath -c "import sys; print(f'{sys.version_info[0]}.{sys.version_info[1]}')" 2>$null
        if ($LASTEXITCODE -eq 0 -and $out -match '^\d+\.\d+$') {
            $parts = $out.Trim().Split('.')
            if ([int]$parts[0] -eq 3 -and [int]$parts[1] -ge 11) { return $true }
        }
    } catch {}
    return $false
}

function Find-SystemPythonOffPath {
    # 1. PATH (excluding broken WindowsApps alias via Test-RealPython)
    $cmdPy = Get-Command python -ErrorAction SilentlyContinue
    if ($cmdPy -and (Test-RealPython $cmdPy.Source)) { return $cmdPy.Source }

    # 2. Windows py.exe Launcher (`C:\Windows\py.exe`)
    foreach ($pyLauncher in @("$env:WINDIR\py.exe", "$env:LOCALAPPDATA\Programs\Python\Launcher\py.exe")) {
        if (Test-Path $pyLauncher) {
            foreach ($verArg in @("-3.12", "-3.13", "-3.11", "-3")) {
                try {
                    $resolved = (& $pyLauncher $verArg -c "import sys; print(sys.executable)" 2>$null | Select-Object -Last 1)
                    if ($LASTEXITCODE -eq 0 -and $resolved -and (Test-RealPython $resolved.Trim())) {
                        return $resolved.Trim()
                    }
                } catch {}
            }
        }
    }

    # 3. Standard & User-Space Install Locations + uv Managed Pythons
    $patterns = @(
        "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python3*\python.exe",
        "$env:ProgramFiles\Python312\python.exe",
        "$env:ProgramFiles\Python3*\python.exe",
        "$env:APPDATA\uv\python\cpython-3.12*\python.exe",
        "$env:LOCALAPPDATA\uv\python\cpython-3.12*\python.exe",
        "$HOME\scoop\apps\python*\current\python.exe",
        "$HOME\miniconda3\python.exe",
        "$HOME\anaconda3\python.exe"
    )
    foreach ($pat in $patterns) {
        $hits = Get-Item -Path $pat -ErrorAction SilentlyContinue | Sort-Object FullName -Descending
        foreach ($h in $hits) {
            if (Test-RealPython $h.FullName) { return $h.FullName }
        }
    }

    # 4. Windows Registry (`PythonCore\*\InstallPath`)
    foreach ($regBase in @("HKCU:\Software\Python\PythonCore", "HKLM:\Software\Python\PythonCore", "HKLM:\Software\WOW6432Node\Python\PythonCore")) {
        if (Test-Path $regBase) {
            foreach ($verKey in (Get-ChildItem $regBase -ErrorAction SilentlyContinue | Sort-Object PSChildName -Descending)) {
                $ip = Join-Path $verKey.PSPath "InstallPath"
                if (Test-Path $ip) {
                    $exeProp = Get-RegValue -Path $ip -Name "ExecutablePath"
                    if ($exeProp -and (Test-RealPython $exeProp)) { return $exeProp }
                    $dirProp = Get-RegValue -Path $ip -Name ""
                    if ($dirProp) {
                        $cand = Join-Path $dirProp "python.exe"
                        if (Test-RealPython $cand) { return $cand }
                    }
                }
            }
        }
    }
    return $null
}

# ---------------------------------------------------------------------------
# Helper: Find or Auto-Download Standalone `uv.exe` (Zero Prerequisites!)
# ---------------------------------------------------------------------------
function Find-UvExe {
    $cmdUv = Get-Command uv -ErrorAction SilentlyContinue
    if ($cmdUv -and (Test-Path $cmdUv.Source)) { return $cmdUv.Source }

    $cands = @(
        "$HOME\.local\bin\uv.exe",
        "$HOME\.cargo\bin\uv.exe",
        "$HOME\scoop\shims\uv.exe"
    )
    $wingetHits = Get-ChildItem -Path "$env:LOCALAPPDATA\Microsoft\WinGet\Packages\astral-sh.uv*" -Filter "uv.exe" -Recurse -ErrorAction SilentlyContinue
    foreach ($wh in $wingetHits) { $cands += $wh.FullName }

    foreach ($c in $cands) {
        if ($c -and (Test-Path -LiteralPath $c)) { return $c }
    }
    return $null
}

function Install-StandaloneUv {
    $binDir = Join-Path $HOME ".local\bin"
    New-Item -ItemType Directory -Force -Path $binDir | Out-Null
    $dstUv = Join-Path $binDir "uv.exe"
    if (Test-Path $dstUv) { return $dstUv }

    $arch = if ($env:PROCESSOR_ARCHITECTURE -eq "ARM64") { "aarch64-pc-windows-msvc" } else { "x86_64-pc-windows-msvc" }
    $zipUrl = "https://github.com/astral-sh/uv/releases/latest/download/uv-$arch.zip"
    $tmpZip = Join-Path ([System.IO.Path]::GetTempPath()) "velum_uv_$([guid]::NewGuid().ToString('N')).zip"
    $tmpExt = Join-Path ([System.IO.Path]::GetTempPath()) "velum_uv_ext_$([guid]::NewGuid().ToString('N'))"

    Write-Host "  Downloading standalone Python bootstrapper (uv) from GitHub Releases..." -ForegroundColor Cyan
    try {
        Invoke-WebRequest -Uri $zipUrl -OutFile $tmpZip -UseBasicParsing
        Expand-Archive -Path $tmpZip -DestinationPath $tmpExt -Force
        $extractedUv = Get-ChildItem -Path $tmpExt -Filter "uv.exe" -Recurse | Select-Object -First 1
        if ($extractedUv) {
            Copy-Item -LiteralPath $extractedUv.FullName -Destination $dstUv -Force
        }
    } finally {
        Remove-Item $tmpZip -Force -ErrorAction SilentlyContinue
        Remove-Item $tmpExt -Recurse -Force -ErrorAction SilentlyContinue
    }
    if (Test-Path $dstUv) { return $dstUv }
    return $null
}

# ---------------------------------------------------------------------------
# Helper: Deep 10-Source Blender Auto-Discovery on Windows
# ---------------------------------------------------------------------------
function Test-RealBlender {
    param([string]$ExePath)
    if ([string]::IsNullOrWhiteSpace($ExePath) -or -not (Test-Path -LiteralPath $ExePath)) { return $null }
    try {
        $verOut = (& $ExePath --version 2>$null | Select-Object -First 1)
        if ($LASTEXITCODE -eq 0 -and $verOut -match 'Blender\s+(\d+)\.(\d+)') {
            return $verOut.Trim()
        }
    } catch {}
    return $null
}

function Find-BlenderWindows {
    $raw = New-Object System.Collections.Generic.List[string]

    # 1. Saved user config (~/.velum-forge/config.json) & env var
    $cfgFile = Join-Path $HOME ".velum-forge\config.json"
    if (Test-Path $cfgFile) {
        try {
            $cfg = Get-Content $cfgFile -Raw | ConvertFrom-Json
            if ($cfg.PSObject.Properties["blender_exe"] -and $cfg.blender_exe) { $raw.Add([string]$cfg.blender_exe) }
        } catch {}
    }
    if ($env:VELUM_BLENDER_EXE) { $raw.Add($env:VELUM_BLENDER_EXE) }

    # 2. PATH
    $bCmd = Get-Command blender -ErrorAction SilentlyContinue
    if ($bCmd) { $raw.Add($bCmd.Source) }

    # 3. All mounted filesystem drives (C:..Z:) + Blender Launcher + Scoop + Chocolatey
    $drives = Get-PSDrive -PSProvider FileSystem -ErrorAction SilentlyContinue | Where-Object { $_.Root -match '^[A-Z]:\\$' }
    foreach ($d in $drives) {
        $r = $d.Root
        foreach ($pat in @(
            "${r}Program Files\Blender Foundation\Blender*\blender.exe",
            "${r}Program Files (x86)\Blender Foundation\Blender*\blender.exe",
            "${r}Blender Foundation\Blender*\blender.exe",
            "${r}Blender*\blender.exe",
            "${r}Blender*\Blender*\blender.exe",
            "${r}Tools\Blender*\blender.exe",
            "${r}Apps\Blender*\blender.exe",
            "${r}SteamLibrary\steamapps\common\Blender\blender.exe",
            "${r}Steam\steamapps\common\Blender\blender.exe",
            "${r}Games\SteamLibrary\steamapps\common\Blender\blender.exe"
        )) {
            Get-Item -Path $pat -ErrorAction SilentlyContinue | Sort-Object FullName -Descending | ForEach-Object { $raw.Add($_.FullName) }
        }
    }

    foreach ($userPat in @(
        "$env:LOCALAPPDATA\Programs\Blender Foundation\Blender*\blender.exe",
        "$HOME\Blender Launcher\*\*\blender.exe",
        "$env:LOCALAPPDATA\Blender Launcher\*\*\blender.exe",
        "$HOME\scoop\apps\blender\*\blender.exe",
        "$env:ProgramData\chocolatey\lib\blender*\tools\*\blender.exe",
        "$HOME\Desktop\blender*\blender.exe",
        "$HOME\OneDrive\Desktop\blender*\blender.exe",
        "$HOME\Downloads\blender*\blender.exe"
    )) {
        Get-Item -Path $userPat -ErrorAction SilentlyContinue | Sort-Object FullName -Descending | ForEach-Object { $raw.Add($_.FullName) }
    }

    # 4. Steam libraryfolders.vdf across all drives
    foreach ($sReg in @("HKCU:\Software\Valve\Steam", "HKLM:\SOFTWARE\WOW6432Node\Valve\Steam", "HKLM:\SOFTWARE\Valve\Steam")) {
        if (Test-Path $sReg) {
            $sp = Get-RegValue -Path $sReg -Name "SteamPath"
            if (-not $sp) { $sp = Get-RegValue -Path $sReg -Name "InstallPath" }
            if ($sp -and (Test-Path $sp)) {
                $raw.Add((Join-Path $sp "steamapps\common\Blender\blender.exe"))
                $vdf = Join-Path $sp "steamapps\libraryfolders.vdf"
                if (Test-Path $vdf) {
                    $vdfTxt = Get-Content $vdf -Raw -ErrorAction SilentlyContinue
                    if ($vdfTxt) {
                        foreach ($m in [regex]::Matches($vdfTxt, '"path"\s+"([^"]+)"')) {
                            $libPath = $m.Groups[1].Value -replace '\\\\', '\'
                            $raw.Add((Join-Path $libPath "steamapps\common\Blender\blender.exe"))
                        }
                    }
                }
            }
        }
    }

    # 5. Registry App Paths, .blend ProgId Association, Uninstall keys & Shell MuiCache
    foreach ($ap in @(
        "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\blender.exe",
        "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\blender.exe"
    )) {
        $v = Get-RegValue -Path $ap -Name ""
        if ($v) { $raw.Add(($v -replace '^"|"$', '')) }
    }

    # .blend Open Command
    try {
        $progIds = @("blendfile", "blend_auto_file")
        $pidVal = Get-RegValue -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\FileExts\.blend\UserChoice" -Name "ProgId"
        if ($pidVal) { $progIds = @($pidVal) + $progIds }
        foreach ($pidName in $progIds) {
            foreach ($clsRoot in @("Registry::HKEY_CLASSES_ROOT\$pidName\shell\open\command", "HKCU:\Software\Classes\$pidName\shell\open\command")) {
                $cmdStr = Get-RegValue -Path $clsRoot -Name ""
                if ($cmdStr -and $cmdStr -match '"([^"]+\.exe)"') {
                    $exeCand = $Matches[1]
                    $sib = Join-Path (Split-Path $exeCand -Parent) "blender.exe"
                    if (Test-Path $sib) { $raw.Add($sib) } else { $raw.Add($exeCand) }
                }
            }
        }
    } catch {}

    # Uninstall entries
    foreach ($uRoot in @(
        "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*",
        "HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*",
        "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*"
    )) {
        Get-ItemProperty $uRoot -ErrorAction SilentlyContinue | Where-Object {
            $_.PSObject.Properties["DisplayName"] -and $_.DisplayName -like "*Blender*"
        } | ForEach-Object {
            if ($_.PSObject.Properties["InstallLocation"] -and $_.InstallLocation) {
                $raw.Add((Join-Path ($_.InstallLocation.Trim(' "')) "blender.exe"))
            }
            if ($_.PSObject.Properties["DisplayIcon"] -and $_.DisplayIcon) {
                $ico = ($_.DisplayIcon -split ',')[0].Trim(' "')
                $raw.Add((Join-Path (Split-Path $ico -Parent) "blender.exe"))
            }
        }
    }

    # Shell MuiCache (catches portable .zip Blender anywhere on disk!)
    foreach ($mui in @(
        "HKCU:\Software\Classes\Local Settings\Software\Microsoft\Windows\Shell\MuiCache",
        "HKCU:\Software\Microsoft\Windows NT\CurrentVersion\AppCompatFlags\Compatibility Assistant\Store"
    )) {
        if (Test-Path $mui) {
            $props = (Get-ItemProperty $mui -ErrorAction SilentlyContinue).PSObject.Properties
            foreach ($p in $props) {
                if ($p.Name -match '(?i)(.+?blender(?:-launcher)?\.exe)') {
                    $hitExe = $Matches[1].Trim(' "')
                    $sib = Join-Path (Split-Path $hitExe -Parent) "blender.exe"
                    if (Test-Path $sib) { $raw.Add($sib) } elseif (Test-Path $hitExe) { $raw.Add($hitExe) }
                }
            }
        }
    }

    # Microsoft Store AppxPackage
    try {
        Get-AppxPackage *Blender* -ErrorAction SilentlyContinue | ForEach-Object {
            if ($_.InstallLocation) {
                $raw.Add((Join-Path $_.InstallLocation "Blender\blender.exe"))
                $raw.Add((Join-Path $_.InstallLocation "blender.exe"))
            }
        }
    } catch {}

    # Deduplicate, verify runnable `--version`, and pick highest version!
    $seen = @{}
    $bestExe = $null
    $bestScore = -1
    foreach ($cand in $raw) {
        if ([string]::IsNullOrWhiteSpace($cand)) { continue }
        if (-not (Test-Path -LiteralPath $cand)) { continue }
        $full = (Resolve-Path -LiteralPath $cand).Path
        $key = $full.ToLowerInvariant()
        if ($seen.ContainsKey($key)) { continue }
        $seen[$key] = $true

        $verLine = Test-RealBlender $full
        if ($verLine -and $verLine -match 'Blender\s+(\d+)\.(\d+)(?:\.(\d+))?') {
            $score = ([int]$Matches[1] * 10000) + ([int]$Matches[2] * 100) + ([int]($Matches[3] -as [int]))
            if ($score -gt $bestScore) {
                $bestScore = $score
                $bestExe = $full
            }
        }
    }
    return $bestExe
}

# ---------------------------------------------------------------------------
# Step 0: Resolve Repo Root (Git Clone OR Git-less ZIP Download if run via irm)
# ---------------------------------------------------------------------------
if ($PSScriptRoot -and (Test-Path (Join-Path $PSScriptRoot "pyproject.toml"))) {
    $RepoRoot = (Resolve-Path $PSScriptRoot).Path
} else {
    if ([string]::IsNullOrWhiteSpace($InstallDir)) {
        $InstallDir = Join-Path $HOME "VelumForge"
    }
    if (-not (Test-Path (Join-Path $InstallDir "pyproject.toml"))) {
        $gitCmd = Get-Command git -ErrorAction SilentlyContinue
        if (-not $gitCmd -and (Test-Path "$env:ProgramFiles\Git\cmd\git.exe")) {
            $gitExe = "$env:ProgramFiles\Git\cmd\git.exe"
        } elseif ($gitCmd) {
            $gitExe = $gitCmd.Source
        } else {
            $gitExe = $null
        }

        if ($gitExe) {
            Write-Host "[Velum Forge] Cloning https://github.com/velumix/velum-forge.git -> $InstallDir ..." -ForegroundColor Cyan
            & $gitExe clone https://github.com/velumix/velum-forge.git $InstallDir
        } else {
            Write-Host "[Velum Forge] Git not detected — downloading velum-forge archive via HTTPS..." -ForegroundColor Cyan
            $tmpRepoZip = Join-Path ([System.IO.Path]::GetTempPath()) "velum_forge_main.zip"
            $tmpRepoExt = Join-Path ([System.IO.Path]::GetTempPath()) "velum_forge_ext_$([guid]::NewGuid().ToString('N'))"
            Invoke-WebRequest -Uri "https://github.com/velumix/velum-forge/archive/refs/heads/main.zip" -OutFile $tmpRepoZip -UseBasicParsing
            Expand-Archive -Path $tmpRepoZip -DestinationPath $tmpRepoExt -Force
            New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
            Copy-Item -Path (Join-Path $tmpRepoExt "velum-forge-main\*") -Destination $InstallDir -Recurse -Force
            Remove-Item $tmpRepoZip -Force -ErrorAction SilentlyContinue
            Remove-Item $tmpRepoExt -Recurse -Force -ErrorAction SilentlyContinue
        }
    }
    $RepoRoot = (Resolve-Path $InstallDir).Path
}

# ---------------------------------------------------------------------------
# Zero-Python-Required Native Windows .NET Setup Wizard (`-Gui` Mode)
# ---------------------------------------------------------------------------
if ($Gui) {
    Add-Type -AssemblyName System.Windows.Forms
    Add-Type -AssemblyName System.Drawing
    [System.Windows.Forms.Application]::EnableVisualStyles()

    $form = New-Object System.Windows.Forms.Form
    $form.Text = "Velum Forge v1.0 — 3D CAD, PBR & AI Workflow Installer"
    $form.Size = New-Object System.Drawing.Size(760, 590)
    $form.StartPosition = "CenterScreen"
    $form.BackColor = [System.Drawing.Color]::FromArgb(11, 17, 32)
    $form.ForeColor = [System.Drawing.Color]::FromArgb(241, 245, 249)
    $form.FormBorderStyle = "FixedDialog"
    $form.MaximizeBox = $false

    $lblTitle = New-Object System.Windows.Forms.Label
    $lblTitle.Text = "Velum Forge — Setup & AI Workflow Installer"
    $lblTitle.Font = New-Object System.Drawing.Font("Segoe UI", 15, [System.Drawing.FontStyle]::Bold)
    $lblTitle.AutoSize = $true
    $lblTitle.Location = New-Object System.Drawing.Point(24, 18)
    $form.Controls.Add($lblTitle)

    $lblSub = New-Object System.Windows.Forms.Label
    $lblSub.Text = "Auto-installs Python 3.12 (even if Python is missing!), detects Blender across all drives/Steam, & installs AI skills."
    $lblSub.Font = New-Object System.Drawing.Font("Segoe UI", 9.5)
    $lblSub.ForeColor = [System.Drawing.Color]::FromArgb(148, 163, 184)
    $lblSub.AutoSize = $true
    $lblSub.Location = New-Object System.Drawing.Point(26, 50)
    $form.Controls.Add($lblSub)

    $lblBlender = New-Object System.Windows.Forms.Label
    $lblBlender.Text = "Blender Executable (auto-detected across Drives, Steam, Registry & Store — or click Browse):"
    $lblBlender.Font = New-Object System.Drawing.Font("Segoe UI", 9.5, [System.Drawing.FontStyle]::Bold)
    $lblBlender.AutoSize = $true
    $lblBlender.Location = New-Object System.Drawing.Point(26, 86)
    $form.Controls.Add($lblBlender)

    $txtBlender = New-Object System.Windows.Forms.TextBox
    $txtBlender.Location = New-Object System.Drawing.Point(26, 110)
    $txtBlender.Size = New-Object System.Drawing.Size(586, 28)
    $txtBlender.BackColor = [System.Drawing.Color]::FromArgb(17, 28, 51)
    $txtBlender.ForeColor = [System.Drawing.Color]::FromArgb(103, 232, 249)
    $txtBlender.Font = New-Object System.Drawing.Font("Consolas", 10)
    $detectedB = Find-BlenderWindows
    $txtBlender.Text = if ($detectedB) { $detectedB } else { "" }
    $form.Controls.Add($txtBlender)

    $btnBrowse = New-Object System.Windows.Forms.Button
    $btnBrowse.Text = "Browse..."
    $btnBrowse.Location = New-Object System.Drawing.Point(622, 108)
    $btnBrowse.Size = New-Object System.Drawing.Size(98, 29)
    $btnBrowse.BackColor = [System.Drawing.Color]::FromArgb(30, 41, 59)
    $btnBrowse.ForeColor = [System.Drawing.Color]::White
    $btnBrowse.FlatStyle = "Flat"
    $btnBrowse.Add_Click({
        $ofd = New-Object System.Windows.Forms.OpenFileDialog
        $ofd.Title = "Select blender.exe"
        $ofd.Filter = "Blender (blender.exe)|blender.exe|Executables (*.exe)|*.exe"
        if ($ofd.ShowDialog() -eq "OK") { $txtBlender.Text = $ofd.FileName }
    })
    $form.Controls.Add($btnBrowse)

    $chkLaunch = New-Object System.Windows.Forms.CheckBox
    $chkLaunch.Text = "Launch Velum Forge Studio App immediately after installation completes"
    $chkLaunch.Checked = $true
    $chkLaunch.AutoSize = $true
    $chkLaunch.Font = New-Object System.Drawing.Font("Segoe UI", 10)
    $chkLaunch.Location = New-Object System.Drawing.Point(28, 150)
    $form.Controls.Add($chkLaunch)

    $txtLog = New-Object System.Windows.Forms.TextBox
    $txtLog.Multiline = $true
    $txtLog.ScrollBars = "Vertical"
    $txtLog.ReadOnly = $true
    $txtLog.Location = New-Object System.Drawing.Point(26, 184)
    $txtLog.Size = New-Object System.Drawing.Size(694, 300)
    $txtLog.BackColor = [System.Drawing.Color]::FromArgb(5, 8, 17)
    $txtLog.ForeColor = [System.Drawing.Color]::FromArgb(165, 243, 252)
    $txtLog.Font = New-Object System.Drawing.Font("Consolas", 9.5)
    $initMsg = if ($detectedB) { "[OK] Auto-detected Blender: $detectedB`r`n" } else { "[INFO] Blender not auto-detected yet — click 'Browse...' above if installed in a custom folder.`r`n" }
    $txtLog.Text = "${initMsg}Ready. Click 'Install & Configure Workflow' below.`r`n"
    $form.Controls.Add($txtLog)

    $btnInstall = New-Object System.Windows.Forms.Button
    $btnInstall.Text = "Install & Configure Workflow"
    $btnInstall.Location = New-Object System.Drawing.Point(485, 498)
    $btnInstall.Size = New-Object System.Drawing.Size(235, 38)
    $btnInstall.BackColor = [System.Drawing.Color]::FromArgb(2, 132, 199)
    $btnInstall.ForeColor = [System.Drawing.Color]::White
    $btnInstall.Font = New-Object System.Drawing.Font("Segoe UI", 10, [System.Drawing.FontStyle]::Bold)
    $btnInstall.FlatStyle = "Flat"

    $selfScript = Join-Path $RepoRoot "install.ps1"
    $btnInstall.Add_Click({
        $btnInstall.Enabled = $false
        $btnInstall.Text = "Installing..."
        $txtLog.AppendText("`r`nStarting installation...`r`n")

        $argList = @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "`"$selfScript`"")
        if (-not [string]::IsNullOrWhiteSpace($txtBlender.Text)) {
            $argList += @("-BlenderPath", "`"$($txtBlender.Text.Trim())`"")
        }
        if ($chkLaunch.Checked) { $argList += "-LaunchStudio" }

        $psi = New-Object System.Diagnostics.ProcessStartInfo
        $psi.FileName = "powershell.exe"
        $psi.Arguments = ($argList -join " ")
        $psi.UseShellExecute = $false
        $psi.RedirectStandardOutput = $true
        $psi.RedirectStandardError = $true
        $psi.CreateNoWindow = $true

        $proc = New-Object System.Diagnostics.Process
        $proc.StartInfo = $psi
        [void]$proc.Start()

        while (-not $proc.HasExited) {
            while (-not $proc.StandardOutput.EndOfStream) {
                $line = $proc.StandardOutput.ReadLine()
                $txtLog.AppendText("$line`r`n")
                [System.Windows.Forms.Application]::DoEvents()
            }
            Start-Sleep -Milliseconds 60
            [System.Windows.Forms.Application]::DoEvents()
        }
        $remOut = $proc.StandardOutput.ReadToEnd()
        $remErr = $proc.StandardError.ReadToEnd()
        if ($remOut) { $txtLog.AppendText("$remOut`r`n") }
        if ($remErr) { $txtLog.AppendText("$remErr`r`n") }

        if ($proc.ExitCode -eq 0) {
            $btnInstall.Text = "Completed!"
            $btnInstall.BackColor = [System.Drawing.Color]::FromArgb(22, 163, 74)
            if ($chkLaunch.Checked) {
                $form.Close()
            }
        } else {
            $btnInstall.Enabled = $true
            $btnInstall.Text = "Retry Install"
        }
    })
    $form.Controls.Add($btnInstall)

    [void]$form.ShowDialog()
    exit 0
}

# ---------------------------------------------------------------------------
# Main Unattended / CLI Installer Flow
# ---------------------------------------------------------------------------
Write-Host "`n=== Velum Forge 1.0 Installer ===" -ForegroundColor Cyan
Write-Host "Repository: $RepoRoot"

# Save explicit or auto-detected Blender path into ~/.velum-forge/config.json right away!
$CfgDir = Join-Path $HOME ".velum-forge"
New-Item -ItemType Directory -Force -Path $CfgDir | Out-Null
$CfgPath = Join-Path $CfgDir "config.json"
$CfgObj = @{}
if (Test-Path $CfgPath) {
    try {
        $existing = Get-Content $CfgPath -Raw | ConvertFrom-Json
        foreach ($p in $existing.PSObject.Properties) { $CfgObj[$p.Name] = $p.Value }
    } catch {}
}

$ChosenBlender = if (-not [string]::IsNullOrWhiteSpace($BlenderPath) -and (Test-Path -LiteralPath $BlenderPath)) {
    (Resolve-Path -LiteralPath $BlenderPath).Path
} else {
    Find-BlenderWindows
}
if ($ChosenBlender) {
    $CfgObj["blender_exe"] = $ChosenBlender
    Write-Host "[OK] Detected Blender: $ChosenBlender" -ForegroundColor Green
} else {
    Write-Host "[WARN] Blender not detected yet. Install Blender 5.2 LTS+ or click 'Locate blender.exe' inside Velum Forge Studio." -ForegroundColor Yellow
}

$VenvDir = Join-Path $RepoRoot ".venv"
$VenvPy = Join-Path $VenvDir "Scripts\python.exe"

if (-not $SkipVenv) {
    $UvExe = Find-UvExe
    if (-not $UvExe) {
        Write-Host "[1/4] Python/uv not on PATH — auto-bootstrapping standalone uv + CPython 3.12..." -ForegroundColor Cyan
        $UvExe = Install-StandaloneUv
    }

    if ($UvExe) {
        Write-Host "[1/4] Provisioning standalone Python 3.12 CAD environment via uv ($UvExe)..." -ForegroundColor Cyan
        & $UvExe python install 3.12
        & $UvExe venv $VenvDir --python 3.12 --allow-existing
        & $UvExe pip install --python $VenvPy -e $RepoRoot
    } else {
        Write-Host "[1/4] Searching machine for off-PATH Python 3.11+ installation..." -ForegroundColor Cyan
        $SysPy = Find-SystemPythonOffPath
        if (-not $SysPy) {
            throw "Could not download uv and no local Python 3.11+ was found on disk. Check internet connection and retry."
        }
        Write-Host "  Found Python at: $SysPy" -ForegroundColor Green
        if (-not (Test-RealPython $VenvPy)) {
            & $SysPy -m venv $VenvDir
        }
        & $VenvPy -m pip install --upgrade pip
        & $VenvPy -m pip install -e $RepoRoot
    }
}

$RunPy = if (Test-RealPython $VenvPy) { $VenvPy } else { Find-SystemPythonOffPath }
if (-not $RunPy) {
    throw "Python virtual environment setup did not produce a runnable interpreter at $VenvPy"
}

$CfgObj["python_exe"] = $RunPy
$CfgObj | ConvertTo-Json -Depth 5 | Set-Content -Path $CfgPath -Encoding UTF8

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
if (-not $UserPath) { $UserPath = "" }
if ($UserPath -notlike "*$BinDir*") {
    $NewPath = if ($UserPath) { "$BinDir;$UserPath" } else { $BinDir }
    [Environment]::SetEnvironmentVariable("Path", $NewPath, "User")
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
