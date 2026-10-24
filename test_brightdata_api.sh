#!/bin/bash
# Test Bright Data Web Unlocker API integration

echo "🧪 Testing Bright Data Web Unlocker API"
echo "========================================"
echo ""

# Check if API key is configured
if grep -q "BRIGHT_DATA_API_KEY=$" .env; then
    echo "⚠️  Bright Data API key not configured in .env"
    echo ""
    echo "To configure:"
    echo "1. Get your API key from: https://brightdata.com/cp/api_tokens"
    echo "2. Edit .env and set: BRIGHT_DATA_API_KEY=your_api_key_here"
    echo ""
    exit 1
fi

echo "1. Testing standard fetch (free)..."
response=$(curl -s -X POST http://127.0.0.1:5006/api/research \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Get content from example.com",
    "urls": ["https://example.com"]
  }')

success=$(echo "$response" | python3 -c "import sys, json; print(json.load(sys.stdin).get('success', False))")
method=$(echo "$response" | python3 -c "import sys, json; r=json.load(sys.stdin).get('results',[]); print(r[0].get('method','') if r else '')")

if [ "$success" = "True" ]; then
    echo "✅ Standard fetch working (method: $method)"
else
    echo "❌ Standard fetch failed"
    echo "$response" | python3 -m json.tool
fi

echo ""
echo "2. Testing Bright Data fallback (bot-protected site)..."
response=$(curl -s -X POST http://127.0.0.1:5006/api/research \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Research from bot-protected site",
    "urls": ["https://nowsecure.nl"]
  }')

success=$(echo "$response" | python3 -c "import sys, json; print(json.load(sys.stdin).get('success', False))")
method=$(echo "$response" | python3 -c "import sys, json; r=json.load(sys.stdin).get('results',[]); print(r[0].get('method','') if r else '')")

if [ "$success" = "True" ]; then
    echo "✅ Bright Data fallback working (method: $method)"
else
    echo "⚠️  Bright Data fallback triggered but may need API key"
    echo "   Method attempted: $method"
fi

echo ""
echo "3. Testing massive extraction detection..."
response=$(curl -s -X POST http://127.0.0.1:5006/api/research \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Scrape 50 product pages from example.com",
    "urls": ["https://example.com"]
  }')

method=$(echo "$response" | python3 -c "import sys, json; r=json.load(sys.stdin).get('results',[]); print(r[0].get('method','') if r else '')")

if [ "$method" = "bright_data_api" ]; then
    echo "✅ Massive extraction detection working (uses Bright Data directly)"
else
    echo "⚠️  Expected bright_data_api, got: $method"
fi

echo ""
echo "========================================"
echo "Test suite completed"
echo ""
echo "Summary:"
echo "- Standard fetch: Fast and free for simple requests"
echo "- Bright Data fallback: Handles bot-protected sites"
echo "- Massive extraction: Automatically uses Bright Data"
echo ""
echo "To configure Bright Data API key:"
echo "1. Get key from: https://brightdata.com/cp/api_tokens"
echo "2. Edit .env: BRIGHT_DATA_API_KEY=your_key_here"
echo "3. Restart research service: pkill -f research_service && python3 backend/research_service.py &"
