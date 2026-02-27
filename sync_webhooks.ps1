# sync_webhooks.ps1
# Downloads webhook events from Render cloud to local PC

param(
    [string]$Date = (Get-Date -Format "yyyy-MM-dd")
)

$url = "https://pyquant-alexander.onrender.com/events/$Date"
$output = "Output\webhooks\events_$Date.json"

Write-Host "================================================" -ForegroundColor Cyan
Write-Host " PyQuant Alexander - Webhook Sync" -ForegroundColor Green
Write-Host " Date: $Date" -ForegroundColor Yellow
Write-Host "================================================" -ForegroundColor Cyan
Write-Host ""

try {
    Write-Host "Downloading events from Render..." -ForegroundColor Cyan
    
    Invoke-WebRequest -Uri $url -OutFile $output -UseBasicParsing -ErrorAction Stop
    
    if (Test-Path $output) {
        $fileSize = (Get-Item $output).Length
        Write-Host "✅ Success: Downloaded $fileSize bytes" -ForegroundColor Green
        Write-Host "   Saved to: $output" -ForegroundColor Gray
        
        # Show event count (handle NDJSON format)
        $content = Get-Content $output -Raw
        if ($content.StartsWith('[')) {
            # JSON array
            $events = $content | ConvertFrom-Json
            Write-Host "   Events: $($events.Count)" -ForegroundColor Gray
        } else {
            # NDJSON - count lines
            $lines = (Get-Content $output | Where-Object { $_.Trim() -ne "" }).Count
            Write-Host "   Events: $lines" -ForegroundColor Gray
        }
        
        exit 0
    } else {
        Write-Host "❌ Failed: File not created" -ForegroundColor Red
        exit 1
    }
    
} catch {
    $statusCode = $_.Exception.Response.StatusCode.value__
    
    if ($statusCode -eq 404) {
        Write-Host "⚠️  No events found for $Date" -ForegroundColor Yellow
        Write-Host "   This is normal if alerts haven't fired yet" -ForegroundColor Gray
        exit 0
    } else {
        Write-Host "❌ Error: $($_.Exception.Message)" -ForegroundColor Red
        exit 1
    }
}