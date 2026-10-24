#!/bin/bash
# Quick check: is the backend running and is the iMessage bridge running?
# Run from project root: ./scripts/check_services.sh

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT"

[ -f .env ] && set -a && source .env && set +a

BACKEND_PORT="${SERVER_PORT:-8003}"
BRIDGE_PORT="${IMESSAGE_BRIDGE_PORT:-8100}"
AGENT_PORT="${AGENT_PORT:-8005}"

echo "Checking Cortex-AI services..."
echo ""

# Backend (required for messages to be handled)
if curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:${BACKEND_PORT}/health" 2>/dev/null | grep -q 200; then
  echo "  Backend (port ${BACKEND_PORT}):  RUNNING"
else
  echo "  Backend (port ${BACKEND_PORT}):  NOT RUNNING"
  echo "    -> Messages will not be processed. Start with: cd backend && uv run main.py"
  echo "    -> Or run full stack: ./run_order.sh"
fi

# Agent-S (required for desktop tasks from messages/UI)
if curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:${AGENT_PORT}/health" 2>/dev/null | grep -q 200; then
  BODY=$(curl -s "http://127.0.0.1:${AGENT_PORT}/health" 2>/dev/null || true)
  if echo "$BODY" | grep -q '"agent_configured":true'; then
    echo "  Agent-S (port ${AGENT_PORT}):  RUNNING (agent configured)"
  else
    echo "  Agent-S (port ${AGENT_PORT}):  RUNNING (agent NOT configured - check logs)"
  fi
else
  echo "  Agent-S (port ${AGENT_PORT}):  NOT RUNNING"
  echo "    -> Desktop tasks will not run. Set ANTHROPIC_API_KEY in .env and run: cd Agent-S && ./run_claude.sh"
  echo "    -> Or start full stack: ./run_order.sh"
fi

# iMessage bridge (required for iMessage -> backend)
if curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:${BRIDGE_PORT}/health" 2>/dev/null | grep -q 200; then
  echo "  iMessage bridge (port ${BRIDGE_PORT}):  RUNNING"
else
  echo "  iMessage bridge (port ${BRIDGE_PORT}):  NOT RUNNING"
  echo "    -> iMessage will not be forwarded to the backend. Start with: cd backend && uv run imessage_bridge.py"
  echo "    -> Ensure .env is loaded (SERVER_PORT, IMESSAGE_BRIDGE_PORT, etc.)"
fi

echo ""
echo "To start everything: ./run_order.sh"
echo "To start only backend + iMessage: cd backend && uv run main.py & uv run imessage_bridge.py &"
