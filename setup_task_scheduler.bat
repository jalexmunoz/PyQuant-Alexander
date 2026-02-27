@echo off
REM ========================================
REM PyQuant Alexander - Task Scheduler Setup
REM Configures automated daily execution
REM ========================================

echo ========================================
echo PyQuant Alexander - Task Scheduler Setup
echo ========================================
echo.

REM Delete old task if exists
schtasks /delete /tn "\PyQuant\PyQuantShadowMode" /f >nul 2>&1
schtasks /delete /tn "\PyQuant\PyQuant_Shadow_AUTOMATED" /f >nul 2>&1

REM Create new automated task
schtasks /create ^
    /tn "\PyQuant\PyQuant_Shadow_AUTOMATED" ^
    /tr "cmd.exe /c \"C:\pyquant_alexander\run_daily_automated.bat\"" ^
    /sc daily ^
    /st 19:15 ^
    /rl highest ^
    /f

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ========================================
    echo SUCCESS: Task created successfully
    echo ========================================
    echo Task Name: PyQuant_Shadow_AUTOMATED
    echo Schedule:  Daily at 7:15 PM ET
    echo Script:    C:\pyquant_alexander\run_daily_automated.bat
    echo ========================================
    echo.
    echo To verify: Open Task Scheduler and check \PyQuant\
    echo.
) else (
    echo.
    echo ERROR: Failed to create task
    echo Run this script as Administrator
    echo.
)

pause