#!/usr/bin/env bash

# // llm: {
# //     provider: 'anthropic',
# //     options: {
# //         model: 'claude-sonnet-4-20250514',
# //         apiKey: process.env.ANTHROPIC_API_KEY
# //     }
# // },

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
[ -f "$SCRIPT_DIR/.env" ] && source "$SCRIPT_DIR/.env"
[ -f "$SCRIPT_DIR/../.env" ] && source "$SCRIPT_DIR/../.env"
: "${ANTHROPIC_API_KEY:?ANTHROPIC_API_KEY environment variable must be set}"
uv run -m src.s3.app \
    --provider anthropic \
    --model claude-sonnet-4-20250514 \
    --model_api_key "${ANTHROPIC_API_KEY}" \
    --ground_provider anthropic \
    --ground_url https://api.anthropic.com \
    --ground_model claude-sonnet-4-20250514 \
    --ground_api_key "${ANTHROPIC_API_KEY}" \
    --grounding_width 1920 \
    --grounding_height 1080 \
    --model_temperature 0.3 \
    --enable_reflection
