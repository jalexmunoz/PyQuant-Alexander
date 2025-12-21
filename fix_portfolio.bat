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
echo   Creating massive commit
echo ================================

git commit -m "feat: Complete automation system - Day 21 Dec 2025

BLOQUE 1 - Automatización:
- GET endpoint en webhook_receiver para descargar eventos
- sync_webhooks.ps1 para descarga automática desde Render
- run_daily_automated.bat para flujo completo
- Parser híbrido JSON array + NDJSON

BLOQUE 2 - Risk Mitigation:
- Deduplicación mejorada con logging detallado
- Heartbeat tracking (status, events, assets)
- Data validation (price>0, SMAs válidas)
- Timezone logging (UTC + local)
- Silence detection script

BLOQUE 3 - Observability:
- Market structure metrics (gap%%, signal, price/SMAs)
- Weekly summary script (uptime, actions, trends)

BLOQUE 4 - Validation:
- Fake webhooks testing
- Task Scheduler configurado y validado
- 2 dry runs exitosos (LastTaskResult=0)

Sistema 100%% automático validado y listo para 90 días OOS."

echo ================================
echo   Pushing to origin/dev
echo ================================

git push origin dev

echo.
echo ✅ Commit + Push completado exitosamente
echo.
pause