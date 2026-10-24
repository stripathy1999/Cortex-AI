# Windows Setup — Shadow-OS

Run and test your Windows-side tasks locally.

## Prerequisites

- **Python 3.12+** with [uv](https://docs.astral.sh/uv/) (`pip install uv` or `irm https://astral.sh/uv/install.ps1 | iex`)
- **Node.js 18+**
- **Anthropic API key** (or OpenAI/Grok for Agent-S)

## 1. Backend Setup

```powershell
cd Treehacks\backend
uv sync
uv add ".[vision]"   # Optional: for vision service (MediaPipe)
```

## 2. Agent-S Setup

```powershell
cd Treehacks\Agent-S
uv sync
```

Create `Treehacks\.env` (or copy from `.env.example`):

```
AGENT_PORT=8001
AGENT_HOST=127.0.0.1
UI_PORT=8002
UI_HOST=127.0.0.1
SERVER_PORT=8003
SERVER_HOST=127.0.0.1
IMESSAGE_BRIDGE_PORT=8100
IMESSAGE_BRIDGE_HOST=127.0.0.1
ANTHROPIC_API_KEY=sk-ant-your-key
```

## 3. Frontend Setup

```powershell
cd Treehacks\frontend
npm install
```

## 4. Run the Stack

### Option A: PowerShell script

```powershell
cd Treehacks
$env:ANTHROPIC_API_KEY = "sk-ant-your-key"
.\run_windows.ps1
```

### Option B: Manual (3 terminals)

**Terminal 1 — Backend:**
```powershell
cd Treehacks\backend
uv run main.py
```

**Terminal 2 — Agent-S:**
```powershell
cd Treehacks\Agent-S
$env:ANTHROPIC_API_KEY = "sk-ant-your-key"
uv run -m src.s3.app --provider anthropic --model claude-sonnet-4-20250514 --model_api_key $env:ANTHROPIC_API_KEY --ground_provider anthropic --ground_url https://api.anthropic.com --ground_model claude-sonnet-4-20250514 --ground_api_key $env:ANTHROPIC_API_KEY --grounding_width 1920 --grounding_height 1080 --model_temperature 1.0
```

**Terminal 3 — Frontend:**
```powershell
cd Treehacks\frontend
npm start
```

## 5. Vision Mirror (Optional)

**Terminal 4 — Vision service:**
```powershell
cd Treehacks\backend
uv add ".[vision]"
uv run vision_service.py
```

**Terminal 5 — Cursor service:**
```powershell
cd Treehacks\backend
uv run cursor_service.py
```

**Terminal 6 — Vision-Cursor bridge (webcam → cursor):**
```powershell
cd Treehacks\backend
uv run vision_cursor_bridge.py
```

## 6. Test

- **Frontend:** Open the app, type a prompt, press Enter or click the Shadow (clock) button
- **Vision:** `curl -X POST http://localhost:5003/api/vision/frame -F "image=@hand.png"`
- **Cursor:** `uv run test_vision_cursor.py --cursor-only`
