@echo off
cd /d C:\pyquant_alexander

echo ========================================
echo PyQuant Alexander - Automated Daily Run
echo %date% %time%
echo ========================================
echo.

REM 1. Sync webhooks from Render
echo [1/3] Syncing webhooks from Render...
powershell -ExecutionPolicy Bypass -File sync_webhooks.ps1
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Webhook sync failed
    exit /b 1
)
echo.

REM 2. Run shadow mode (using venv Python)
echo [2/3] Running shadow mode...
C:\pyquant_alexander\.venv\Scripts\python.exe runners\run_shadow_mode.py
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Shadow mode failed
    exit /b 1
)
echo.

REM 3. Write run marker
echo [3/3] Recording run status...
if not exist Output\logs mkdir Output\logs
echo RUN_OK %date% %time% >> Output\logs\automation_log.txt
echo.

echo ========================================
echo Completed successfully
echo ========================================
exit /b 0