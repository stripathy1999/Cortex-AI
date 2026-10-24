# Bright Data Integration - Smart Web Intelligence

## Overview

Bright Data integration provides intelligent web scraping that automatically handles:
- **Bot detection** (Cloudflare, CAPTCHA, 403 errors)
- **Rate limiting** (429 errors)
- **Massive data extraction** (50+ pages, bulk scraping)
- **Protected content** (login walls, geo-restrictions)

The system automatically chooses between lightweight fetch and Bright Data proxy based on task complexity.

## How It Works

```
Research Request
    ↓
Analyze Query
    ↓
┌─────────────────────┐
│ Massive extraction? │
│ (50+ pages, bulk)   │
└─────────┬───────────┘
          │
    ┌─────┴─────┐
    │           │
   YES         NO
    │           │
    ▼           ▼
Bright Data   Standard Fetch
    │           │
    │           ├─ Success → Return
    │           │
    │           ├─ Bot detected (403, CAPTCHA)
    │           │  → Fallback to Bright Data
    │           │
    │           └─ Network error
    │              → Fallback to Bright Data
    │
    ▼
Clean HTML
Remove scripts, ads, nav
Extract main content
    ↓
Return optimized content
```

## Setup

### 1. Get Bright Data Credentials

1. Sign up at https://brightdata.com
2. Go to https://brightdata.com/cp/zones
3. Create a new zone (Residential or Datacenter)
4. Copy your credentials:
   - Username: `brd-customer-<customer-id>-zone-<zone-name>`
   - Password: `<zone-password>`

### 2. Configure Environment

Add to `.env`:

```bash
# Bright Data Configuration
BRIGHT_DATA_USERNAME=brd-customer-hl_12345678-zone-residential
BRIGHT_DATA_PASSWORD=your_zone_password_here
```

### 3. Start Research Service

```bash
python3 backend/research_service.py &
```

Service runs on port **5006**

## Usage

### Via API

**Standard research (auto-routing):**
```bash
curl -X POST http://127.0.0.1:5006/api/research \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Research competitor pricing from https://example.com/products",
    "urls": ["https://example.com/products"]
  }'
```

**Force Bright Data (massive extraction):**
```bash
curl -X POST http://127.0.0.1:5006/api/research \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Scrape 50 product pages from Amazon",
    "urls": ["https://amazon.com/s?k=laptop"]
  }'
```

### Via Poke/iMessage

Send to Poke (+1 650-444-0949):

**Simple research:**
```
"research latest AI news from techcrunch.com"
```

**Competitor pricing:**
```
"scrape pricing from https://competitor.com/products"
```

**Massive extraction:**
```
"extract all product listings from 50 pages on amazon.com"
```

## Automatic Routing Logic

### Standard Fetch (Fast, Free)
Used when:
- ✅ Simple, single-page requests
- ✅ Public content without protection
- ✅ No bot detection expected

**Examples:**
- "Research latest news from TechCrunch"
- "Get content from blog post"
- "Extract text from Wikipedia page"

### Bright Data (Powerful, Paid)
Used when:
- ⚠️ Bot detection encountered (403, CAPTCHA, Cloudflare)
- ⚠️ Massive extraction keywords detected ("50+ pages", "bulk", "scrape all")
- ⚠️ Standard fetch fails
- ⚠️ Rate limiting (429 errors)

**Examples:**
- "Scrape 100 product pages from Amazon"
- "Extract pricing from protected competitor site"
- "Bypass Cloudflare and get content"
- "Crawl entire product catalog"

## Detection Patterns

### Bot Detection
Automatically detected:
- Status codes: 403, 429, 503
- Content patterns: "captcha", "cloudflare", "access denied", "bot detected"

### Massive Extraction
Keywords trigger Bright Data:
- "scrape", "extract", "crawl", "massive", "bulk"
- "all pages", "multiple pages", "entire site"
- "50+", "100+", "many pages"

## HTML Cleaning

All responses are cleaned to save tokens:
- ✅ Removes: scripts, styles, nav, footer, ads, iframes
- ✅ Extracts: main content, article text
- ✅ Cleans: excessive whitespace, comments
- ✅ Optimizes: for LLM processing

**Before cleaning:** 500KB HTML
**After cleaning:** 50KB clean text

## Response Format

```json
{
  "success": true,
  "query": "Research competitor pricing",
  "total_urls": 1,
  "successful": 1,
  "failed": 0,
  "results": [
    {
      "success": true,
      "url": "https://example.com",
      "status_code": 200,
      "content": "Cleaned text content...",
      "method": "bright_data",
      "content_length": 5234
    }
  ],
  "summary": "Successfully extracted 1/1 URLs"
}
```

## Integration with Agent-S

The research tool is automatically available to Agent-S:

**Tool registration:**
```python
# Agent-S/src/s3/tools/web_research.py
{
  "name": "intelligent_research",
  "description": "Smart web research with bot-detection bypass",
  "parameters": {
    "query": "Natural language research task",
    "urls": "List of URLs to research"
  }
}
```

**Agent-S will automatically use it when:**
- User asks to research protected sites
- Standard web tools fail with 403/CAPTCHA
- Task involves scraping multiple pages
- Competitor analysis or pricing research

## Cost Optimization

### Free Tier (Standard Fetch)
- ✅ Most requests use standard fetch first
- ✅ Only fallback to Bright Data when needed
- ✅ Automatic bot-detection triggers fallback

### Bright Data Pricing
- **Residential proxies:** ~$8.40/GB
- **Datacenter proxies:** ~$0.60/GB
- **Pay-as-you-go:** No monthly minimums

**Typical costs:**
- Single page: ~$0.01
- 10 pages: ~$0.10
- 100 pages: ~$1.00

## Testing

### Test Standard Fetch

```bash
curl -X POST http://127.0.0.1:5006/api/research \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Get content from example.com",
    "urls": ["https://example.com"]
  }'
```

**Expected:** Uses standard fetch (method: "standard")

### Test Bot Detection Fallback

```bash
curl -X POST http://127.0.0.1:5006/api/research \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Research from bot-protected site",
    "urls": ["https://nowsecure.nl"]
  }'
```

**Expected:** Detects bot blocking → Falls back to Bright Data

### Test Massive Extraction

```bash
curl -X POST http://127.0.0.1:5006/api/research \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Scrape 50 product pages",
    "urls": ["https://example.com/products"]
  }'
```

**Expected:** Uses Bright Data directly (method: "bright_data")

## Real-World Examples

### Example 1: Competitor Pricing

**Request:**
```
"Research laptop pricing from https://competitor.com/laptops"
```

**Flow:**
1. Try standard fetch
2. Encounter 403 (bot detected)
3. Fallback to Bright Data
4. Successfully extract pricing
5. Return cleaned content

### Example 2: Amazon Product Research

**Request:**
```
"Extract all laptop listings from Amazon under $1000"
```

**Flow:**
1. Detect massive extraction keywords
2. Use Bright Data directly
3. Scrape multiple pages
4. Clean and aggregate results
5. Return optimized data

### Example 3: News Research

**Request:**
```
"Get latest AI news from TechCrunch"
```

**Flow:**
1. Use standard fetch (simple request)
2. Successfully extract content
3. Clean HTML
4. Return article text

## Troubleshooting

### Bright Data credentials not working

```bash
# Test credentials
curl -x brd.superproxy.io:22225 \
  -U "YOUR_USERNAME:YOUR_PASSWORD" \
  https://lumtest.com/myip.json
```

**Should return:** Your proxy IP and location

### Standard fetch always failing

```bash
# Check if site is bot-protected
curl -I https://target-site.com

# If you see Cloudflare headers or 403:
# → Bright Data will automatically be used
```

### Research service not responding

```bash
# Check service status
curl http://127.0.0.1:5006/health

# Restart if needed
pkill -f research_service
python3 backend/research_service.py &
```

### High Bright Data costs

**Optimization tips:**
- Let standard fetch try first (automatic)
- Use datacenter proxies for non-residential sites
- Cache results when possible
- Limit massive extraction to necessary pages

## Security Notes

- ✅ Credentials stored in `.env` (gitignored)
- ✅ Proxy connection encrypted (HTTPS)
- ✅ No credentials logged
- ✅ HTML cleaned before storage

## Advanced Configuration

### Custom Proxy Settings

Edit `backend/intelligent_research.py`:

```python
# Use datacenter proxy (cheaper)
BRIGHT_DATA_PROXY = "brd.superproxy.io:22225"  # Residential
# or
BRIGHT_DATA_PROXY = "brd.superproxy.io:22225"  # Datacenter
```

### Custom Detection Patterns

Add to `BOT_DETECTION_PATTERNS`:

```python
BOT_DETECTION_PATTERNS = [
    "captcha", "recaptcha", "cloudflare",
    "your-custom-pattern"  # Add custom patterns
]
```

### Timeout Configuration

```python
# Standard fetch timeout
result = self._fetch_standard(url, timeout=10)

# Bright Data timeout (longer for complex pages)
result = self._fetch_bright_data(url, timeout=30)
```

## Monitoring

### Check Usage

```bash
# View Bright Data dashboard
open https://brightdata.com/cp/zones

# Check recent requests
# See bandwidth usage
# Monitor costs
```

### Logs

```bash
# View research service logs
tail -f logs/research_service.log

# Check for bot detection
grep "bot_detected" logs/research_service.log

# Check Bright Data usage
grep "bright_data" logs/research_service.log
```

## Next Steps

1. **Configure credentials** in `.env`
2. **Test with simple request** to verify setup
3. **Try bot-protected site** to test fallback
4. **Monitor costs** in Bright Data dashboard
5. **Integrate with Poke** for natural language research

The system is production-ready and will intelligently route between standard and Bright Data based on task requirements!
