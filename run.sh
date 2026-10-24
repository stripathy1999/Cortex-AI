#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Load .env for all subprocesses
[ -f .env ] && set -a && source .env && set +a

# Kill all background jobs on exit or Ctrl+C
trap 'kill 0' EXIT INT

# Start backend services
cd backend
uv run main.py &
uv run imessage_bridge.py &
uv run call.py &
cd ..

# Start Agent S
cd Agent-S
# ./run_demo_fast.sh & # What we used in demo video. Needs UI-TARS on Hugging Face
# ./run_demo_best.sh & # Agent S3 settings. Needs UI-TARS on Hugging Face
./run_claude.sh & # Claude Sonnet - Best for computer-use tasks
# ./run_grok.sh & # Fastest option
# ./run_openai.sh & # Likely most widely available option
cd ..

# Start frontend
cd frontend
npm start &
cd ..

# Wait for everything
wait

