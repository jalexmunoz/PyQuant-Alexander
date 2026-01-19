@echo off
REM PyQuant Alexander - Shadow Mode Automated Runner
REM Executes daily shadow mode processing from Windows Task Scheduler

cd /d C:\pyquant_alexander

call .venv\Scripts\activate

echo [RUNNER] Iniciando Shadow Mode automatizado...
echo [RUNNER] Fecha: %date% %time%

python runners/run_shadow_mode.py

if %errorlevel% neq 0 (
    echo [ERROR] El script falló con código %errorlevel%
    pause
) else (
    echo [SUCCESS] Ejecución completada.
)

deactivate
