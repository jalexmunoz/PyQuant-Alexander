@echo off
cd /d C:\pyquant_alexander

set LOG_DIR=Output\logs
if not exist %LOG_DIR% mkdir %LOG_DIR%

set TIMESTAMP=%date:~-4%%date:~-10,2%%date:~-7,2%_%time:~0,2%%time:~3,2%%time:~6,2%
set TIMESTAMP=%TIMESTAMP: =0%
set LOG_FILE=%LOG_DIR%\shadow_mode_%TIMESTAMP%.log

echo [%date% %time%] Starting Shadow Mode... > %LOG_FILE%
echo ======================================== >> %LOG_FILE%

python runners\run_shadow_mode.py >> %LOG_FILE% 2>&1

echo. >> %LOG_FILE%
echo [%date% %time%] Completed. >> %LOG_FILE%

type %LOG_FILE%

if "%1"=="" timeout /t 5

exit /b 0