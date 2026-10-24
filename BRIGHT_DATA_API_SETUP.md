# Bright Data Web Unlocker API - Quick Setup

## ✅ What's Ready

Bright Data integration is implemented and ready to use. Just add your API key!

## 🚀 Quick Setup (2 minutes)

### 1. Get Your API Key

1. Go to: https://brightdata.com/cp/api_tokens
2. Click "Create API Token"
3. Copy your API key (starts with `brd-...`)

### 2. Add to .env

Edit `.env` and add:

```bash
BRIGHT_DATA_API_KEY=your_api_key_here
BRIGHT_DATA_ZONE=web_unlocker1
```

### 3. Restart Research Service

Run from the **backend** directory so dependencies (e.g. `requests`, `flask`) are available:

```bash
pkill -f research_service
cd backend && uv run research_service.py &
```

### 4. Test It

```bash
./test_brightdata_api.sh
```

## 📝 Example API Call

```bash
curl https://api.brightdata.com/request \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -d '{
    "zone": "web_unlocker1",
    "url": "https://example.com",
    "format": "raw"
  }'
```

## 🎯 How It Works

### Automatic Smart Routing

```
Your Request
    ↓
Standard Fetch (Free)
    ↓
Success? → YES → Return content
    ↓ NO
Bot detected (403/CAPTCHA)?
    ↓ YES
Bright Data API (Paid)
    ↓
Bypass protection → Return content
```

### When Bright Data is Used

**Automatically triggered:**
- ✅ Bot detection (403, CAPTCHA, Cloudflare)
- ✅ Rate limiting (429 errors)
- ✅ Massive extraction keywords ("scrape 50 pages", "bulk extract")
- ✅ Standard fetch fails

**Always free first:**
- Standard fetch tries first
- Only uses Bright Data when needed
- Saves money automatically

## 💰 Pricing

**Standard Fetch:** FREE
**Bright Data:** Pay-as-you-go
- Single page: ~$0.01
- 10 pages: ~$0.10
- 100 pages: ~$1.00

## 📱 Usage Examples

### Via API

```bash
curl -X POST http://127.0.0.1:5006/api/research \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Research competitor pricing",
    "urls": ["https://competitor.com/products"]
  }'
```

### Via Poke

Send to +1 (650) 444-0949:

```
"research latest AI news from techcrunch"
"scrape pricing from competitor.com"
"extract product data from 50 pages"
```

### Via Agent-S

Agent-S automatically uses it when:
- Standard web tools fail
- User asks to scrape protected sites
- Competitor analysis needed

## 🧪 Testing

Run the test suite:

```bash
./test_brightdata_api.sh
```

**Tests:**
1. ✅ Standard fetch (free)
2. ✅ Bot detection fallback
3. ✅ Massive extraction detection

## 🔧 Configuration

### Default Settings

```bash
BRIGHT_DATA_API_KEY=your_key_here
BRIGHT_DATA_ZONE=web_unlocker1
```

### Custom Zone

If you have a different zone:

```bash
BRIGHT_DATA_ZONE=your_custom_zone
```

## 📊 Monitoring

### Check Usage

View dashboard: https://brightdata.com/cp/zones

### View Logs

```bash
# Research service logs
tail -f logs/research_service.log

# Check Bright Data usage
grep "bright_data_api" logs/research_service.log
```

## ✅ Status Check

```bash
# Test standard fetch
curl -X POST http://127.0.0.1:5006/api/research \
  -H "Content-Type: application/json" \
  -d '{"query": "test", "urls": ["https://example.com"]}'

# Should return: "method": "standard"
```

## 🎁 What You Get

✅ **Automatic bot bypass** - Handles Cloudflare, CAPTCHA, 403 errors
✅ **Smart routing** - Free first, paid only when needed
✅ **Cost optimization** - Minimal Bright Data usage
✅ **Clean content** - HTML cleaned and optimized
✅ **Poke integration** - Natural language research
✅ **Agent-S ready** - Automatic tool selection

## 🚦 Ready to Use

1. Add API key to `.env`
2. Restart research service
3. Test with `./test_brightdata_api.sh`
4. Start researching via Poke or API

That's it! Your intelligent web research system is ready.

## Use cases and example prompts

- **Scrape/caption/store** → Bright Data (content saved to `data/scraped/`).
- **Other browser tasks** → Browserbase/Stagehand first; if it fails, Bright Data fallback when the message contains URLs.

See **[docs/BRIGHT_DATA_USE_CASES_AND_PROMPTS.md](docs/BRIGHT_DATA_USE_CASES_AND_PROMPTS.md)** for example prompts and use cases.
