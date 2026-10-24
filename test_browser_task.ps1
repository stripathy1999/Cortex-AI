# Quick test for browser tasks (Stagehand)
# Run this AFTER starting: main.py, Agent-S, stagehand_service.py

$backend = "http://127.0.0.1:8003"

Write-Host "Testing browser task: 'Open Chrome and search Sakshi Tripathy on Google'" -ForegroundColor Cyan
$body = @{
    text = "Open Chrome and search Sakshi Tripathy on Google"
    phone_number = "test:curl"
    display_name = "Test"
} | ConvertTo-Json

try {
    $response = Invoke-RestMethod -Uri "$backend/api/new_imessage" -Method POST -Body $body -ContentType "application/json"
    Write-Host "Response:" -ForegroundColor Green
    $response | ConvertTo-Json -Depth 3
} catch {
    Write-Host "Error: $_" -ForegroundColor Red
    Write-Host "Make sure main.py (port 8003), Agent-S, and stagehand_service.py are running."
}
