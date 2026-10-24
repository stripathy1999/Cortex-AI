#!/bin/bash
# Run the message pipeline (iMessage bridge + call.py) permanently: restart on exit.
# Use from project root: ./scripts/run_message_pipeline_forever.sh
# Or run_order.sh uses this so the pipeline never stays down.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT"

# Load .env so SERVER_HOST, SERVER_PORT, ALLOWED_IMESSAGE_CONTACT, etc. are set
set -a
[ -f .env ] && source .env
set +a

# Ensure backend URL is set for the bridge (default from SERVER_HOST:SERVER_PORT)
export BACKEND_BASE_URL="${BACKEND_BASE_URL:-http://${SERVER_HOST:-127.0.0.1}:${SERVER_PORT:-8003}}"

cd backend || exit 1

run_bridge() {
  while true; do
    uv run imessage_bridge.py
    code=$?
    echo "[$(date '+%H:%M:%S')] iMessage bridge exited (code=$code), restarting in 2s..."
    sleep 2
  done
}

run_call() {
  while true; do
    uv run call.py
    code=$?
    echo "[$(date '+%H:%M:%S')] call.py exited (code=$code), restarting in 2s..."
    sleep 2
  done
}

# Start bridge first so it binds to port immediately (like Discord)
run_bridge &
sleep 2
run_call &

echo "Message pipeline running: iMessage bridge (instant poll) + call.py. Restart on exit enabled."
wait
