# Shadow-OS — Windows Run Script
# Full Windows stack: Telegram/Discord messaging, voice, vision, Agent-S

$ErrorActionPreference = "Stop"
$ProjectRoot = $PSScriptRoot

Write-Host "Starting Shadow-OS (Windows stack)..." -ForegroundColor Cyan
Write-Host "  - Windows message bridge (Discord/Slack/WhatsApp) - new window"
Write-Host "  - Stagehand (browser automation) - new window"
Write-Host "  - Backend (main.py) - new window"
Write-Host "  - Agent-S - new window"
Write-Host "  - Call service (optional, for voice) - new window"
Write-Host "  - Frontend (Electron) - this window"
Write-Host ""

# Load .env for all processes
$envPath = Join-Path $ProjectRoot ".env"
if (Test-Path $envPath) {
    Get-Content $envPath | ForEach-Object {
        if ($_ -match '^\s*([^#][^=]+)=(.*)$') {
            $key = $matches[1].Trim()
            $value = $matches[2].Trim().Trim('"').Trim("'")
            [Environment]::SetEnvironmentVariable($key, $value, "Process")
        }
    }
}

# Start Windows message bridge (Telegram or Discord - replaces iMessage)
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$ProjectRoot\backend'; uv run windows_message_bridge.py"

# Start backend in new window
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$ProjectRoot\backend'; uv run main.py"

# Start Agent-S in new window (reads ANTHROPIC_API_KEY from .env)
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$ProjectRoot\Agent-S'; uv run -m src.s3.app --provider anthropic --model claude-sonnet-4-20250514 --ground_provider anthropic --ground_url https://api.anthropic.com --ground_model claude-sonnet-4-20250514 --grounding_width 1920 --grounding_height 1080 --model_temperature 1.0"

# Start Stagehand (browser automation for Chrome/Google/YouTube)
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$ProjectRoot\backend'; uv run python stagehand_service.py"

# Start call service (voice - works with mic, Teams/Skype via VB-Audio Cable)
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$ProjectRoot\backend'; uv run call.py"

Write-Host "Waiting for services to start..." -ForegroundColor Gray
Start-Sleep -Seconds 8

# Start frontend (blocking)
Set-Location (Join-Path $ProjectRoot "frontend")
npm start
