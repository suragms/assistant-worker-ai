#Requires -Version 5.1
<#
.SYNOPSIS
    Build Assistant Worker for Windows.
.DESCRIPTION
    Cleans previous output, runs PyInstaller, and reports the result.
    Optionally compiles the Inno Setup installer.
.PARAMETER Debug
    Build the console-enabled debug EXE instead of the production windowed one.
.PARAMETER Installer
    After a successful build, compile the Inno Setup installer.
.EXAMPLE
    .\scripts\build_windows.ps1
    .\scripts\build_windows.ps1 -Debug
    .\scripts\build_windows.ps1 -Installer
#>
param(
    [switch]$Debug,
    [switch]$Installer
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Root   = Split-Path -Parent $PSScriptRoot
$Dist   = Join-Path $Root "dist"
$Build  = Join-Path $Root "build"
$Spec   = if ($Debug) { "AssistantWorker-debug.spec" } else { "AssistantWorker.spec" }
$ExeDir = if ($Debug) { "AssistantWorker-debug" } else { "AssistantWorker" }
$ExeName = if ($Debug) { "AssistantWorker-debug.exe" } else { "AssistantWorker.exe" }

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  Assistant Worker Build$(if ($Debug) { ' (DEBUG)' })" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

# -- 1. Python check ------------------------------------------------------
$py = $null
foreach ($candidate in @("py", "python")) {
    try {
        $null = & $candidate --version 2>&1
        $py = $candidate; break
    } catch { }
}
if (-not $py) { Write-Error "Python not found on PATH." }
Write-Host "[1/6] Python: $( & $py --version 2>&1 )" -ForegroundColor Green

# -- 2. PyInstaller check -------------------------------------------------
try {
    & $py -c "import PyInstaller" 2>$null
} catch {
    Write-Host "Installing PyInstaller..." -ForegroundColor Yellow
    & $py -m pip install pyinstaller --quiet
}
Write-Host "[2/6] PyInstaller: OK" -ForegroundColor Green

# -- 3. Compile & Test checks ---------------------------------------------
Set-Location $Root
Write-Host "[3/7] Compile check..." -ForegroundColor Green
& $py -m compileall . -q 2>&1 | Out-Null
Write-Host "      done" -ForegroundColor Green

Write-Host "[4/7] Running test suites (_test_ui.py & test_voice_panel.py)..." -ForegroundColor Green
& $py _test_ui.py
if ($LASTEXITCODE -ne 0) { Write-Error "Smoke tests (_test_ui.py) failed." }
& $py test_voice_panel.py
if ($LASTEXITCODE -ne 0) { Write-Error "Voice panel tests (test_voice_panel.py) failed." }
Write-Host "      tests passed" -ForegroundColor Green

# -- 5. Clean -------------------------------------------------------------
Write-Host "[5/7] Cleaning old build artefacts..." -ForegroundColor Green
if (Test-Path $Build)  { Remove-Item $Build  -Recurse -Force }
$oldDist = Join-Path $Dist $ExeDir
if (Test-Path $oldDist) { Remove-Item $oldDist -Recurse -Force }
Write-Host "      done" -ForegroundColor Green

# -- 6. PyInstaller -------------------------------------------------------
Write-Host "[6/7] Running PyInstaller ($Spec)..." -ForegroundColor Green
& $py -m PyInstaller $Spec --noconfirm
if ($LASTEXITCODE -ne 0) {
    Write-Error "PyInstaller failed - see output above."
}
Write-Host "      done" -ForegroundColor Green

# -- 7. Report ------------------------------------------------------------
$exePath = Join-Path $Dist (Join-Path $ExeDir $ExeName)
if (Test-Path $exePath) {
    Write-Host ""
    Write-Host "============================================================" -ForegroundColor Green
    Write-Host "  SUCCESS" -ForegroundColor Green
    Write-Host "  EXE: $exePath" -ForegroundColor Green
    Write-Host "============================================================" -ForegroundColor Green
} else {
    Write-Error "EXE not found after build: $exePath"
}

# -- Optional: Inno Setup installer ---------------------------------------
if ($Installer -and -not $Debug) {
    $isccCandidates = @(
        "$env:LOCALAPPDATA\Programs\Antigravity IDE\resources\app\node_modules\innosetup\bin\ISCC.exe",
        "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
        "C:\Program Files\Inno Setup 6\ISCC.exe"
    )
    $iscc = $null
    foreach ($c in $isccCandidates) {
        if (Test-Path $c) {
            $iscc = $c
            break
        }
    }
    if ($iscc) {
        Write-Host ""
        Write-Host "Building installer with Inno Setup ($iscc)..." -ForegroundColor Cyan
        & $iscc (Join-Path $Root "installer\AssistantWorker.iss")
        if ($LASTEXITCODE -eq 0) {
            $setupSrc = Join-Path $Root "installer\Output\AssistantWorker-Setup-1.0.0.exe"
            $relDir = Join-Path $Root "release"
            if (-not (Test-Path $relDir)) { New-Item -ItemType Directory -Path $relDir | Out-Null }
            $setupDst = Join-Path $relDir "AssistantWorker-Setup-1.0.0.exe"
            Copy-Item -Path $setupSrc -Destination $setupDst -Force
            Write-Host "Installer built & copied to release: $setupDst" -ForegroundColor Green

            # Also package the release folder AssistantWorker-1.0.0-Windows-x64
            $relBinDir = Join-Path $relDir "AssistantWorker-1.0.0-Windows-x64"
            if (Test-Path $relBinDir) { Remove-Item $relBinDir -Recurse -Force }
            Copy-Item -Path (Join-Path $Dist $ExeDir) -Destination $relBinDir -Recurse -Force
            Write-Host "Packaged release binaries copied to: $relBinDir" -ForegroundColor Green
        } else {
            Write-Host "Inno Setup failed - see output above." -ForegroundColor Red
        }
    } else {
        Write-Host "Inno Setup not found - skipping installer build." -ForegroundColor Yellow
        Write-Host "Download from: https://jrsoftware.org/isdl.php" -ForegroundColor Yellow
    }
}
