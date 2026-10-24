# Quick service health check - run after starting backend, Agent-S, Stagehand
# Usage: .\scripts\test_services.ps1

$ErrorActionPreference = "Continue"
$backend = "http://127.0.0.1:8003"
$agent = "http://127.0.0.1:8001"
$stagehand = "http://127.0.0.1:5005"

Write-Host "`n=== Service Health Check ===" -ForegroundColor Cyan

# Backend
try {
    $r = Invoke-RestMethod -Uri "$backend/api/contact_links" -Method GET -TimeoutSec 3
    Write-Host "[OK] Backend (main.py) on 8003" -ForegroundColor Green
} catch {
    Write-Host "[FAIL] Backend - is main.py running?" -ForegroundColor Red
}

# Agent-S
try {
    $r = Invoke-RestMethod -Uri "$agent/health" -Method GET -TimeoutSec 3 -ErrorAction Stop
    Write-Host "[OK] Agent-S on 8001" -ForegroundColor Green
} catch {
    Write-Host "[FAIL] Agent-S - is it running?" -ForegroundColor Red
}

# Stagehand
try {
    $r = Invoke-RestMethod -Uri "$stagehand/health" -Method GET -TimeoutSec 3 -ErrorAction Stop
    Write-Host "[OK] Stagehand on 5005" -ForegroundColor Green
} catch {
    Write-Host "[FAIL] Stagehand - run: cd backend; uv run python stagehand_service.py" -ForegroundColor Red
}

Write-Host "`n=== Test browser task (curl) ===" -ForegroundColor Cyan
$body = @{ text = "Open Chrome and search Sakshi Tripathy on Google"; phone_number = "test:curl" } | ConvertTo-Json
try {
    $r = Invoke-RestMethod -Uri "$backend/api/new_imessage" -Method POST -Body $body -ContentType "application/json" -TimeoutSec 120
    Write-Host "Response: $($r | ConvertTo-Json -Compress)" -ForegroundColor Green
} catch {
    Write-Host "Error: $_" -ForegroundColor Red
}
