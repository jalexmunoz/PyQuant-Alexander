@echo off
setlocal
REM ========================================
REM PyQuant Alexander - Shadow Mode Runner
REM v2.1.1 - Render sync + venv python
REM Runs daily at 7:02 PM ET
REM ========================================

cd /d C:\pyquant_alexander
echo [%date% %time%] Starting Shadow Mode...
echo.

REM Prefer venv python (Task Scheduler safe)
set PY=C:\pyquant_alexander\.venv\Scripts\python.exe
if not exist "%PY%" set PY=python

REM STEP 1: Download webhooks from Render
echo [1/2] Syncing webhooks from Render...
"%PY%" utils\sync_from_render.py
if errorlevel 1 (
    echo WARNING: Webhook sync failed, continuing with local data
)
echo.

REM STEP 2: Execute shadow mode
echo [2/2] Processing shadow mode decisions...
"%PY%" runners\run_shadow_mode.py
echo.

echo [%date% %time%] Shadow Mode completed.
echo ========================================
timeout /t 10 /nobreak
exit /b 0
