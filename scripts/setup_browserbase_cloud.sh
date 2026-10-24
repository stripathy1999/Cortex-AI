#!/usr/bin/env bash
# Setup Browserbase cloud with Chrome credentials.
# Run once to create context + sync cookies. Re-run sync_chrome_to_browserbase.py periodically.

set -e
cd "$(dirname "$0")/.."

echo "☁️  Browserbase Cloud Setup"
echo ""

# Check .env
if ! grep -q "BROWSERBASE_API_KEY" .env 2>/dev/null; then
    echo "❌ Add BROWSERBASE_API_KEY and BROWSERBASE_PROJECT_ID to .env"
    exit 1
fi

# 1. Create context (only if missing)
if [ ! -f data/browserbase_context.txt ]; then
    echo "1/2 Creating Browserbase context..."
    python3 scripts/create_browserbase_context.py
else
    echo "1/2 Context exists: $(cat data/browserbase_context.txt | head -c 12)..."
fi
echo ""

# 2. Sync Chrome cookies (use backend uv for decryption on macOS)
echo "2/2 Syncing Chrome cookies to context..."
cd backend && uv run python ../sync_chrome_to_browserbase.py && cd ..
echo ""

echo "✅ Setup complete!"
echo ""
echo "Stagehand will now use your Chrome logins for browser tasks."
echo "Re-run: python3 sync_chrome_to_browserbase.py  (when you log into new sites)"
echo ""
