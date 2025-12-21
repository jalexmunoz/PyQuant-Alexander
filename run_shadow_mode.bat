@echo off
REM ========================================
REM PyQuant Alexander - Shadow Mode Runner
REM Executes daily at 7:15 PM ET
REM ========================================

cd /d C:\pyquant_alexander

echo [%date% %time%] Starting Shadow Mode...
echo.

REM Execute shadow mode script
python runners\run_shadow_mode.py

echo.
echo [%date% %time%] Shadow Mode completed.
echo ========================================
echo.

REM Optional: Keep window open for 10 seconds to see results
timeout /t 10 /nobreak

exit