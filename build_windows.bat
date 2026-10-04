@echo off
REM ============================================================
REM  Assistant Worker — Windows Build Script
REM  Output: dist\AssistantWorker\AssistantWorker.exe
REM ============================================================
setlocal EnableDelayedExpansion

set "ROOT=%~dp0"
set "ROOT=%ROOT:~0,-1%"
set "DIST=%ROOT%\dist"
set "BUILD=%ROOT%\build"

echo.
echo ============================================================
echo   Assistant Worker Build
echo ============================================================
echo.

REM ── 1. Check Python ──────────────────────────────────────────
where py >nul 2>&1
if errorlevel 1 (
    where python >nul 2>&1
    if errorlevel 1 (
        echo ERROR: Python not found on PATH.
        exit /b 1
    )
    set "PY=python"
) else (
    set "PY=py"
)

echo [1/6] Python: OK
%PY% --version

REM ── 2. Install / verify PyInstaller ──────────────────────────
echo.
echo [2/6] Checking PyInstaller...
%PY% -c "import PyInstaller" >nul 2>&1
if errorlevel 1 (
    echo Installing PyInstaller...
    %PY% -m pip install pyinstaller --quiet
    if errorlevel 1 (
        echo ERROR: Failed to install PyInstaller.
        exit /b 1
    )
)
echo PyInstaller: OK

REM ── 3. Compile check ─────────────────────────────────────────
echo.
echo [3/6] Compile check...
cd /d "%ROOT%"
%PY% -m compileall . -q 2>&1
if errorlevel 1 (
    echo WARNING: Compile check found syntax errors — review above output.
    echo Continuing build...
)
echo Compile check: done

REM ── 4. Clean previous build output ───────────────────────────
echo.
echo [4/6] Cleaning old build artefacts...
if exist "%BUILD%" (
    echo Removing build\...
    rmdir /s /q "%BUILD%"
)
if exist "%DIST%\AssistantWorker" (
    echo Removing dist\AssistantWorker\...
    rmdir /s /q "%DIST%\AssistantWorker"
)
echo Clean: done

REM ── 5. Run PyInstaller ───────────────────────────────────────
echo.
echo [5/6] Running PyInstaller...
cd /d "%ROOT%"
%PY% -m PyInstaller AssistantWorker.spec --noconfirm
if errorlevel 1 (
    echo.
    echo ERROR: PyInstaller failed. Check output above.
    echo TIP: Run the debug build to see traceback:
    echo   pyinstaller AssistantWorker-debug.spec
    exit /b 1
)
echo PyInstaller: done

REM ── 6. Report ────────────────────────────────────────────────
echo.
echo [6/6] Build complete.
echo.
if exist "%DIST%\AssistantWorker\AssistantWorker.exe" (
    echo ============================================================
    echo   SUCCESS
    echo   EXE: dist\AssistantWorker\AssistantWorker.exe
    echo ============================================================
) else (
    echo ERROR: EXE not found after build — something went wrong.
    exit /b 1
)

echo.
echo To run the packaged app:
echo   dist\AssistantWorker\AssistantWorker.exe
echo.
echo To build the installer (requires Inno Setup):
echo   "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer\AssistantWorker.iss
echo.
endlocal
