# How to Test Shadow-OS

## Message Your PC: WhatsApp, Discord, Slack

- **WhatsApp** – See [WHATSAPP_SETUP.md](WHATSAPP_SETUP.md) (needs ngrok + Twilio)
- **Discord & Slack** – See [DISCORD_SLACK_SETUP.md](DISCORD_SLACK_SETUP.md) (no ngrok needed)

All three work the same: send a message → agent reads it → PC performs the action.

---

## Quick Test (No messaging app needed)

### 1. Start the core services

Open **3 PowerShell windows** and run (Agent-S reads ANTHROPIC_API_KEY from Treehacks/.env automatically):

**Window 1 – Backend**
```powershell
cd "c:\Users\strip\Documents\Antigravity\TreeHacks New\Treehacks\backend"
uv run main.py
```

**Window 2 – Agent-S** (reads ANTHROPIC_API_KEY from Treehacks/.env)
```powershell
cd "c:\Users\strip\Documents\Antigravity\TreeHacks New\Treehacks\Agent-S"
uv run -m src.s3.app --provider anthropic --model claude-sonnet-4-20250514 --ground_provider anthropic --ground_url https://api.anthropic.com --ground_model claude-sonnet-4-20250514 --grounding_width 1920 --grounding_height 1080 --model_temperature 1.0
```

**Window 3 – Stagehand (browser automation)** (must run from `backend` folder)
- Requires `MODEL_API_KEY` or `OPENAI_API_KEY` in `Treehacks/.env` (for openai/gpt-4o-mini)
```powershell
cd "c:\Users\strip\Documents\Antigravity\TreeHacks New\Treehacks\backend"
uv run python stagehand_service.py
```

Wait until each shows it’s ready (e.g. “Running on http://…”).

### 2. Test a browser task

**Option A – Use the test script:**
```powershell
cd "c:\Users\strip\Documents\Antigravity\TreeHacks New\Treehacks"
.\scripts\test_services.ps1
```

**Option B – Manual curl:**
```powershell
# Test: "Open Chrome and search Sakshi Tripathy on Google"
$body = @{
    text = "Open Chrome and search Sakshi Tripathy on Google"
    phone_number = "test:curl"
    display_name = "Test"
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://127.0.0.1:8003/api/new_imessage" -Method POST -Body $body -ContentType "application/json" -TimeoutSec 120
```

You should see:
- Stagehand window: browser session starts, navigates to Google, runs the search
- Response from the API with the result

### 3. Test another browser task

```powershell
# Test: YouTube Music
$body = @{
    text = "Open Chrome and go to YouTube Music and play some music"
    phone_number = "test:curl"
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://127.0.0.1:8003/api/new_imessage" -Method POST -Body $body -ContentType "application/json"
```

### 4. Test a non-browser task (Agent-S)

```powershell
# Test: Open Notepad (uses Agent-S + pyautogui)
$body = @{
    text = "Open Notepad"
    phone_number = "test:curl"
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://127.0.0.1:8003/api/new_imessage" -Method POST -Body $body -ContentType "application/json"
```

---

## Full stack (with messaging)

### Option A: Discord

1. Add to `.env`:
   ```env
   MESSAGE_SOURCES=discord
   DISCORD_BOT_TOKEN=your-bot-token
   ALLOWED_DISCORD_USER_ID=your-discord-user-id
   ```
2. Run `.\run_windows.ps1`
3. DM your bot in Discord with: `Open Chrome and search Sakshi Tripathy on Google`

### Option B: WhatsApp (Twilio)

1. Create a [Twilio](https://twilio.com) account and get WhatsApp sandbox
2. Add to `.env`:
   ```env
   MESSAGE_SOURCES=whatsapp
   TWILIO_ACCOUNT_SID=your-sid
   TWILIO_AUTH_TOKEN=your-token
   TWILIO_WHATSAPP_NUMBER=whatsapp:+14155238886
   ```
3. Run `ngrok http 8100` and set Twilio webhook to `https://xxx.ngrok.io/webhooks/whatsapp`
4. Run `.\run_windows.ps1`
5. Message the Twilio WhatsApp number from your phone

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| "Stagehand not installed" | `cd backend; uv add stagehand` |
| "Connection refused" to backend | Ensure `main.py` is running on port 8003 |
| Stagehand window shows error | Check BROWSERBASE_* and OPENAI_API_KEY in `.env` |
| Agent-S fails | Check ANTHROPIC_API_KEY in `.env` |
| No reply in WhatsApp/Discord | Message bridge must be running; check Twilio webhook for WhatsApp |
