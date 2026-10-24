# Cortex AI System Status

## Architecture

**Agent-S (Local Desktop)** + **Browserbase (Cloud Browser)** + **Electron UI**

```
┌─────────────────────────────────────────────────────────────┐
│                      Cortex AI System                        │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  Discord/iMessage → Backend → Router                         │
│                                  │                            │
│                    ┌─────────────┴─────────────┐            │
│                    │                             │            │
│              Desktop Task?              Browser Task?         │
│                    │                             │            │
│                    ▼                             ▼            │
│              Agent-S (Local)          Browserbase/Stagehand  │
│              - Notepad                - Chrome automation    │
│              - Calculator             - LinkedIn, Gmail      │
│              - File Explorer          - Web searches         │
│              - Desktop apps           - Cloud browser        │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

## Running Services

### ✅ Core Services
- **Backend API:** http://127.0.0.1:8003
- **Agent-S:** Local desktop automation
- **Stagehand (Browserbase):** http://127.0.0.1:5005
- **Research Service (Bright Data):** http://127.0.0.1:5006
- **Electron UI:** http://localhost:5173

### ✅ Messaging
- **Discord Bot:** Running
- **iMessage Bridge:** http://127.0.0.1:8100

## Configuration

### Browserbase
```bash
STAGEHAND_USE_BROWSERBASE=true
BROWSERBASE_API_KEY=your-browserbase-api-key
BROWSERBASE_PROJECT_ID=your-browserbase-project-id
```

### Bright Data
```bash
BRIGHT_DATA_API_KEY=your-bright-data-api-key
BRIGHT_DATA_ZONE=web_unlocker2
```

## Task Routing

### Desktop Tasks → Agent-S (Fast, Local)
- "Open Notepad"
- "Open Calculator"
- "Open File Explorer"
- Desktop applications

### Browser Tasks → Browserbase (Cloud)
- "Go to google.com"
- "Search for AI news"
- "Open LinkedIn"
- "Check Gmail"
- Any website/browser task

### Research Tasks → Bright Data (Bot Bypass)
- Bot-protected sites
- Massive data extraction
- Competitor research

## Usage

### Via Discord
Send message in Discord channel

### Via iMessage
Send message to configured number

### Via Electron UI
Open http://localhost:5173

### Via API
```bash
curl -X POST http://127.0.0.1:8003/api/new_imessage \
  -H "Content-Type: application/json" \
  -d '{"text": "your command", "phone_number": "+15555550100"}'
```

## Performance

- **Desktop tasks (Agent-S):** Instant (~1-2 seconds)
- **Browser tasks (Browserbase):** ~60-90 seconds (AI-powered)
- **Research tasks (Bright Data):** ~5-10 seconds

## Start All Services

```bash
./start_all_services.sh
```

Or manually:
```bash
python3 backend/main.py &
python3 backend/discord_bot.py &
python3 backend/imessage_bridge.py &
python3 backend/stagehand_service.py &
python3 backend/research_service.py &
cd frontend && npm run dev
```

## System Ready ✅

All services are running and properly configured. The system routes tasks intelligently:
- Desktop → Agent-S (fast)
- Browser → Browserbase (powerful)
- Research → Bright Data (bot bypass)
