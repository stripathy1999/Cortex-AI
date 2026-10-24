#!/bin/bash
# Cortex-AI: One script to start the full stack. Run: ./run_order.sh
# Order: Backend (with health wait) → Agent-S → UI → Stagehand → Research → Message pipeline (iMessage + Discord).
# Architecture: Browser tasks → Backend → Stagehand | Device tasks → Agent-S; messages → backend /api/new_imessage.

# Don't use set -e so one failing service (e.g. Agent-S) doesn't exit the whole script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Load .env
[ -f .env ] && set -a && source .env && set +a

# Kill existing processes
echo "Stopping all services..."
pkill -f "main.py" 2>/dev/null || true
pkill -f "imessage_bridge" 2>/dev/null || true
pkill -f "stagehand_service" 2>/dev/null || true
pkill -f "uv run stagehand" 2>/dev/null || true
pkill -f "call.py" 2>/dev/null || true
pkill -f "windows_message_bridge" 2>/dev/null || true
pkill -f "src.s3.app" 2>/dev/null || true
pkill -f "research_service" 2>/dev/null || true
pkill -f "electron" 2>/dev/null || true
pkill -f "vite" 2>/dev/null || true
sleep 4

trap 'kill 0' EXIT INT

echo ""
echo "1. Starting Backend (required hub for all services)..."
cd backend
uv run main.py &
cd ..
# Wait for backend /health so message bridge and others can rely on it
echo "   Waiting for backend to be ready..."
BACKEND_PORT="${SERVER_PORT:-8003}"
for i in 1 2 3 4 5 6 7 8 9 10; do
  if curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:${BACKEND_PORT}/health" 2>/dev/null | grep -q 200; then
    echo "   Backend is up (port ${BACKEND_PORT})."
    break
  fi
  if [ "$i" -eq 10 ]; then
    echo "   WARNING: Backend did not become ready in time. Continuing anyway."
  fi
  sleep 2
done
sleep 1

# Message pipeline: permanent (restart on exit) – start first so it's ready like Discord
echo ""
echo "2. Starting Message Pipeline (iMessage bridge + call.py, restart forever)..."
"$SCRIPT_DIR/scripts/run_message_pipeline_forever.sh" &
BRIDGE_PORT="${IMESSAGE_BRIDGE_PORT:-8100}"
for i in 1 2 3 4 5 6 7 8 9 10; do
  if curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:${BRIDGE_PORT}/health" 2>/dev/null | grep -q 200; then
    echo "   iMessage bridge is up (port ${BRIDGE_PORT})."
    break
  fi
  [ "$i" -eq 10 ] && echo "   WARNING: iMessage bridge did not respond on ${BRIDGE_PORT}. Check: cd backend && uv run imessage_bridge.py"
  sleep 1
done
# Windows bridge (Discord/Slack/WhatsApp) – port 8101
cd backend
WINDOWS_BRIDGE_PORT=8101 uv run windows_message_bridge.py &
cd ..
sleep 2
echo "   Message pipeline: iMessage (${BRIDGE_PORT}) + call.py + Windows (8101). Tasks → /api/new_imessage."

echo ""
echo "3. Starting Agent-S (port ${AGENT_PORT:-8005})..."
cd Agent-S
./run_claude.sh &
cd ..
AGENT_PORT="${AGENT_PORT:-8005}"
echo "   Waiting for Agent-S..."
for i in 1 2 3 4 5 6 7 8 9 10; do
  if curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:${AGENT_PORT}/health" 2>/dev/null | grep -q 200; then
    echo "   Agent-S is up (port ${AGENT_PORT})."
    break
  fi
  [ "$i" -eq 10 ] && echo "   WARNING: Agent-S did not become ready. Set ANTHROPIC_API_KEY in .env"
  sleep 3
done
sleep 1

echo ""
echo "4. Starting UI (Frontend - Vite + Electron)..."
cd frontend
npm start &
cd ..
for i in 1 2 3 4 5 6 7 8 9 10 11 12; do
  code=$(curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:${UI_PORT:-8002}/" 2>/dev/null || echo "000")
  if [ "$code" = "200" ] || [ "$code" = "404" ] || [ "$code" = "405" ]; then
    echo "   UI API is up (port ${UI_PORT:-8002})."
    break
  fi
  [ "$i" -eq 12 ] && echo "   WARNING: UI API did not become ready."
  sleep 3
done
sleep 2

echo ""
echo "5. Starting Stagehand (Browserbase - port 5005)..."
cd backend
uv run stagehand_service.py &
cd ..
sleep 3

echo ""
echo "6. Starting Bright Data (Research Service - port 5006)..."
if [ -f backend/research_service.py ]; then
  cd backend
  uv run research_service.py &
  cd ..
  sleep 2
  echo "   Research service started"
else
  echo "   (research_service.py not found - skipping)"
fi

echo ""
echo "All services started!"
echo "  - Backend:     http://127.0.0.1:${BACKEND_PORT:-8003}  (messages, FaceTime, Agent-S proxy)"
echo "  - Agent-S:     http://127.0.0.1:${AGENT_PORT:-8005}  (desktop automation)"
echo "  - Stagehand:   http://127.0.0.1:5005  (browser tasks / Browserbase)"
echo "  - Research:    http://127.0.0.1:5006  (Bright Data)"
echo "  - iMessage:    http://127.0.0.1:8100  (Mac messages → backend)"
echo "  - UI (Vite):   http://localhost:5180  (dev server)"
echo "  - UI (API):    http://127.0.0.1:${UI_PORT:-8002}  (Electron receives agent updates)"
echo ""
echo "Show the Cortex UI: open the app from the dock, or click the tray icon (Cortex), or use Cmd+Shift+Space"
echo "Press Ctrl+C to stop all services"
wait || true
# Keep script alive so Ctrl+C kills all; if we exit here, trap would kill background jobs
while true; do sleep 60; done
