# Run message bridge in THIS window so you can see all output and errors
# Use this to debug Discord/Slack/WhatsApp connection issues

$ErrorActionPreference = "Stop"
$TreehacksRoot = Split-Path $PSScriptRoot -Parent
$BackendPath = Join-Path $TreehacksRoot "backend"
$EnvPath = Join-Path $TreehacksRoot ".env"

Write-Host "=== Message Bridge Debug ===" -ForegroundColor Cyan
Write-Host "Backend path: $BackendPath"
Write-Host "Loading .env from: $EnvPath"
Write-Host ""

if (Test-Path $EnvPath) {
    Get-Content $EnvPath | ForEach-Object {
        if ($_ -match '^\s*([^#][^=]+)=(.*)$') {
            $key = $matches[1].Trim()
            $value = $matches[2].Trim().Trim('"').Trim("'")
            [Environment]::SetEnvironmentVariable($key, $value, "Process")
            if ($key -match "TOKEN|SECRET|KEY") {
                Write-Host "  $key = ***" -ForegroundColor Gray
            } else {
                Write-Host "  $key = $value" -ForegroundColor Gray
            }
        }
    }
} else {
    Write-Host "WARNING: .env not found at $EnvPath" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Starting message bridge (Ctrl+C to stop)..." -ForegroundColor Green
Write-Host ""

Set-Location $BackendPath
uv run python windows_message_bridge.py
