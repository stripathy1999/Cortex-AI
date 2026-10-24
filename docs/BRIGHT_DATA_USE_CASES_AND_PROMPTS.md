# Bright Data & Browserbase: Use Cases and Example Prompts

## How routing works

| Task type | First choice | Fallback |
|-----------|--------------|----------|
| **Scrape / caption / extract & store** from the internet | **Bright Data** (research service) | — |
| **Other browser tasks** (search, open site, login, click) | **Browserbase / Stagehand** | **Bright Data** (if Stagehand fails or is down) |

- **Bright Data** is used to fetch and store page content (captions, text, data) and to bypass bot protection. Scrape requests use Bright Data’s **markdown** output so you get clean article/content instead of raw HTML.
- **Browserbase** is used for interactive browser tasks (navigation, forms, multi-step flows). If it fails, the backend can fall back to Bright Data when your message contains URLs.

**Zone:** The app uses `BRIGHT_DATA_ZONE` from `.env` (e.g. `web_unlocker1`). If scraping is blocked or quality is poor, try another zone in the [Bright Data dashboard](https://brightdata.com/cp/zones) (e.g. different proxy type or country) and set `BRIGHT_DATA_ZONE` to that zone name.

---

## When Bright Data is used (scrape / caption / store)

These prompts go **directly** to the research service (Bright Data). Content is saved under `data/scraped/`.

### Example prompts

**Scrape and save**
- *"Scrape the content from https://example.com and store it"*
- *"Extract data from https://news.ycombinator.com and save it"*
- *"Get content from https://techcrunch.com and save to file"*
- *"Scrape and save the main text from https://en.wikipedia.org/wiki/Web_scraping"*

**Caption / capture**
- *"Caption the page at https://example.com and store it"*
- *"Capture from web: https://blog.company.com/post"*
- *"Extract content from https://docs.python.org and save"*

**Fetch and store / save to file**
- *"Get content from https://techcrunch.com and save to file"*
- *"Fetch and save the content from https://example.com"*
- *"Fetch and store the data from https://api.example.com/docs"*
- *"Download content from https://example.com/about"*
- *"Get content from https://example.com and save to a file"*

**From a domain (no full URL)**
- *"Scrape data from example.com"*
- *"Extract content from techcrunch.com"*
- *"Get data from news.ycombinator.com"*  
  (The backend turns these into `https://example.com`, etc.)

---

## When Browserbase is used first (other browser tasks)

These go to **Stagehand / Browserbase** first. If that fails (e.g. service down) and your message contains URLs, the backend falls back to **Bright Data** and returns scraped content.

### Example prompts

**Search and browse**
- *"Search Google for best laptops 2024"*
- *"Open Chrome and search for Python tutorials"*
- *"Go to YouTube and play lofi music"*
- *"Open Gmail"*
- *"Navigate to https://github.com"*

**Multi-step / logged-in**
- *"Go to LinkedIn and open my network"*
- *"Open Twitter and search for #AI"*
- *"Go to Reddit and open the front page"*

**With fallback**
If you say something like: *"Get the content from https://example.com"* and Stagehand is unavailable, the backend will use Bright Data and reply with a summary (and save to `data/scraped/` if it’s a scrape/caption/store-style request).

---

## Use cases

### 1. Competitor / market research
- *"Scrape pricing from https://competitor.com/pricing"*
- *"Extract product listings from https://competitor.com/products and store"*
- *"Get content from https://competitor.com/blog and save"*

### 2. News / articles
- *"Scrape the latest article from https://techcrunch.com"*
- *"Extract and store the main text from https://article-url.com"*
- *"Caption and save the page at https://news-site.com/story"*

### 3. Documentation / reference
- *"Get content from https://docs.python.org/3/library and save"*
- *"Extract data from https://developer.mozilla.org/en-US/docs/Web"*
- *"Scrape and store the FAQ from https://support.example.com"*

### 4. Bot-protected or hard-to-reach sites
- When a site blocks normal browsers (403, CAPTCHA, Cloudflare), the research service uses Bright Data automatically. Same prompts as above; use the URL of the protected page.

### 5. Bulk / many pages
- *"Scrape 50 product pages from https://store.com/products"*  
  (Massive-extraction detection uses Bright Data from the start.)

---

## Where saved files go (local folder on your system)

When you use **chat** (UI or iMessage) and ask to scrape/caption/store, the agent uses Bright Data and saves files on **your machine** in a local folder:

- **Directory:** `data/scraped/` under your project (absolute path, e.g. `/Users/you/Cortex-AI/data/scraped/`)
- **Files:** `YYYYMMDD_HHMMSS_<index>_<url_slug>.txt`
- **Content:** Markdown or cleaned text, one file per URL.

The chat reply includes **"Stored on your system (local folder):"** plus the full path(s) so you can open the file directly.

---

## Quick reference

| You want to… | Say / type… | System uses |
|--------------|-------------|-------------|
| Save page content/caption | "Scrape … from https://…" / "Extract content from …" / "Caption … and store" | Bright Data → save to `data/scraped/` |
| Open a site / search / use the browser | "Search Google for …" / "Go to …" / "Open Gmail" | Browserbase (Stagehand) |
| Open a site but Stagehand is down | "Get content from https://…" (with URL) | Bright Data fallback |

---

## Services to run

1. **Backend** (main.py) – routes messages and calls research/Stagehand.
2. **Research service** (Bright Data) – `cd backend && uv run research_service.py` (port 5006).
3. **Stagehand** (Browserbase) – `cd backend && uv run stagehand_service.py` (port 5005).

`run_order.sh` starts the backend, Stagehand, and the research service together.
