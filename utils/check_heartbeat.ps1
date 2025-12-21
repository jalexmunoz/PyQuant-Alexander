# utils/check_heartbeat.ps1
# Detects if shadow mode hasn't run recently (silence detection)

$heartbeatFile = "Output\heartbeat\last_run.json"

Write-Host "================================================" -ForegroundColor Cyan
Write-Host " PyQuant Alexander - Heartbeat Check" -ForegroundColor Green
Write-Host "================================================" -ForegroundColor Cyan
Write-Host ""

if (-not (Test-Path $heartbeatFile)) {
    Write-Host "❌ CRITICAL: No heartbeat file found!" -ForegroundColor Red
    Write-Host "   Expected: $heartbeatFile" -ForegroundColor Gray
    Write-Host "   System may have never run successfully." -ForegroundColor Yellow
    exit 1
}

try {
    $heartbeat = Get-Content $heartbeatFile | ConvertFrom-Json
    $lastRun = [DateTime]::Parse($heartbeat.last_run)
    $now = Get-Date
    $hoursSince = (New-TimeSpan -Start $lastRun -End $now).TotalHours
    
    Write-Host "Last Run: $($lastRun.ToString('yyyy-MM-dd HH:mm:ss'))" -ForegroundColor Gray
    Write-Host "Time Since: $([math]::Round($hoursSince, 1)) hours ago" -ForegroundColor Gray
    Write-Host "Status: $($heartbeat.status)" -ForegroundColor Gray
    Write-Host "Events Processed: $($heartbeat.events_processed)" -ForegroundColor Gray
    Write-Host ""
    
    # Alert thresholds
    if ($hoursSince -gt 25) {
        Write-Host "⚠️  WARNING: Last run was over 25 hours ago!" -ForegroundColor Red
        Write-Host "   Expected daily runs at 7:15 PM ET" -ForegroundColor Yellow
        Write-Host "   Check Task Scheduler or automation logs" -ForegroundColor Yellow
        exit 1
    } elseif ($hoursSince -gt 24) {
        Write-Host "⚠️  NOTICE: Approaching 24 hour threshold" -ForegroundColor Yellow
        exit 0
    } else {
        Write-Host "✅ Heartbeat OK: System running normally" -ForegroundColor Green
        exit 0
    }
    
} catch {
    Write-Host "❌ ERROR: Failed to parse heartbeat file" -ForegroundColor Red
    Write-Host "   $($_.Exception.Message)" -ForegroundColor Gray
    exit 1
}