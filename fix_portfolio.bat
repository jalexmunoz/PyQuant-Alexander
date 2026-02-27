@echo off
cd /d C:\pyquant_alexander

echo ================================
echo   Adding updated automation files
echo ================================

git add setup_task_scheduler.bat
git add fix_portfolio.bat
git add run_daily_automated.bat
git add sync_webhooks.ps1
git add utils\weekly_summary.py
git add utils\check_heartbeat.ps1
git add utils\heartbeat.py
git add tests\fake_webhooks_test.json
git add runners\run_shadow_mode.py
git add utils\webhook_receiver.py

echo ================================
echo   Creating commit message file
echo ================================

> commit_msg.txt (
echo feat: Complete automation system - Day 21 Dec 2025
echo.
echo BLOQUE 1 - Automatización:
echo - GET endpoint en webhook_receiver para descargar eventos
echo - sync_webhooks.ps1 para descarga automática desde Render
echo - run_daily_automated.bat para flujo completo
echo - Parser híbrido JSON array + NDJSON
echo.
echo BLOQUE 2 - Risk Mitigation:
echo - Deduplicación mejorada con logging detallado
echo - Heartbeat tracking (status, events, assets)
echo - Data validation (price^>0, SMAs válidas)
echo - Timezone logging (UTC + local)
echo - Silence detection script
echo.
echo BLOQUE 3 - Observability:
echo - Market structure metrics (gap%%, signal, price/SMAs)
echo - Weekly summary script (uptime, actions, trends)
echo.
echo BLOQUE 4 - Validation:
echo - Fake webhooks testing
echo - Task Scheduler configurado y validado
echo - 2 dry runs exitosos (LastTaskResult=0)
echo.
echo Sistema 100%% automático validado y listo para 90 días OOS.
)

echo ================================
echo   Committing...
echo ================================

git commit -F commit_msg.txt

echo ================================
echo   Pushing to origin/dev
echo ================================

git push origin dev

del commit_msg.txt

echo.
echo ✅ Commit + Push completado exitosamente
echo.
pause