#!/usr/bin/env python3
"""
Research service: smart web fetch with Bright Data fallback.
- Tries standard HTTP fetch first (free).
- Falls back to Bright Data Web Unlocker API on bot detection (403, CAPTCHA, Cloudflare)
  or when "massive extraction" keywords are detected.
Runs on RESEARCH_SERVICE_PORT (default 5006).
"""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
from flask import Flask, jsonify, request
from flask_cors import CORS

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
if ENV_PATH.exists():
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=ENV_PATH)

logger = logging.getLogger(__name__)
app = Flask(__name__)
CORS(app)

RESEARCH_SERVICE_PORT = int(os.getenv("RESEARCH_SERVICE_PORT", "5006"))
BRIGHT_DATA_API_KEY = (os.getenv("BRIGHT_DATA_API_KEY") or "").strip()
BRIGHT_DATA_ZONE = (os.getenv("BRIGHT_DATA_ZONE") or "web_unlocker2").strip()

# Keywords that indicate bulk/massive extraction → use Bright Data directly
MASSIVE_EXTRACTION_PATTERN = re.compile(
    r"\b(scrape|extract|crawl|bulk|massive|all\s+pages|multiple\s+pages|entire\s+site|"
    r"50\+|100\+|many\s+pages)\b",
    re.I,
)

# Content patterns that suggest bot/CAPTCHA/Cloudflare
BOT_INDICATORS = re.compile(
    r"captcha|cloudflare|access\s+denied|bot\s+detected|blocked|rate\s+limit|checking your browser",
    re.I,
)

# User-Agent for standard fetch (look like a normal browser)
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def _should_use_bright_data_directly(query: str) -> bool:
    """True if query suggests massive/bulk extraction → use Bright Data from the start."""
    if not query:
        return False
    return bool(MASSIVE_EXTRACTION_PATTERN.search(query))


def _looks_like_bot_response(status_code: int, body: str) -> bool:
    """True if response suggests bot blocking."""
    if status_code in (403, 429, 503):
        return True
    if not body:
        return False
    return bool(BOT_INDICATORS.search(body[:8000]))


def _clean_html(html: str, max_chars: int = 200_000) -> str:
    """Strip scripts/styles and reduce to main text for LLM use."""
    if not html:
        return ""
    # Remove script and style blocks
    text = re.sub(r"<script[^>]*>[\s\S]*?</script>", " ", html, flags=re.I)
    text = re.sub(r"<style[^>]*>[\s\S]*?</style>", " ", text, flags=re.I)
    # Strip tags
    text = re.sub(r"<[^>]+>", " ", text)
    # Decode common entities
    text = text.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_chars] if len(text) > max_chars else text


def _fetch_standard(url: str, timeout: int = 25) -> tuple[int, str, Optional[str]]:
    """
    Standard HTTP GET. Returns (status_code, body_text, error_message).
    """
    try:
        r = requests.get(
            url,
            headers=DEFAULT_HEADERS,
            timeout=timeout,
            allow_redirects=True,
        )
        return r.status_code, r.text, None
    except requests.RequestException as e:
        return 0, "", str(e)


def _fetch_bright_data(
    url: str,
    timeout: int = 60,
    use_markdown: bool = False,
) -> tuple[bool, str, Optional[str]]:
    """
    Fetch via Bright Data Web Unlocker API.
    use_markdown: request data_format=markdown for clean article/content extraction.
    Returns (success, content, error_message).
    """
    if not BRIGHT_DATA_API_KEY:
        return False, "", "BRIGHT_DATA_API_KEY not set in .env"
    payload: Dict[str, Any] = {
        "zone": BRIGHT_DATA_ZONE,
        "url": url,
        "format": "raw",
    }
    if use_markdown:
        payload["data_format"] = "markdown"
    try:
        resp = requests.post(
            "https://api.brightdata.com/request",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {BRIGHT_DATA_API_KEY}",
            },
            json=payload,
            timeout=timeout,
        )
        if resp.status_code != 200:
            return False, "", f"Bright Data API returned {resp.status_code}: {resp.text[:500]}"
        return True, resp.text, None
    except requests.RequestException as e:
        return False, "", str(e)


def _fetch_one(
    url: str,
    query: str,
    use_bright_data_first: bool,
    use_markdown: bool = False,
) -> Dict[str, Any]:
    """Fetch a single URL. When use_bright_data_first and use_markdown, use Bright Data with data_format=markdown (no HTML cleaning)."""
    result = {
        "url": url,
        "success": False,
        "status_code": 0,
        "content": "",
        "method": "standard",
        "content_length": 0,
        "error": None,
    }

    if use_bright_data_first and BRIGHT_DATA_API_KEY:
        ok, body, err = _fetch_bright_data(url, use_markdown=use_markdown)
        if use_markdown and not ok and err and ("400" in err or "format" in err.lower()):
            # Zone may not support data_format=markdown; retry with raw HTML
            ok, body, err = _fetch_bright_data(url, use_markdown=False)
            use_markdown = False
        result["method"] = "bright_data_api"
        if ok:
            result["success"] = True
            result["status_code"] = 200
            result["content"] = body if use_markdown else _clean_html(body)
            result["content_length"] = len(result["content"])
        else:
            result["error"] = err
        return result

    # Standard fetch first
    status, body, err = _fetch_standard(url)
    result["status_code"] = status
    if err:
        result["error"] = err
        if BRIGHT_DATA_API_KEY:
            ok, bd_body, bd_err = _fetch_bright_data(url, use_markdown=use_markdown)
            result["method"] = "bright_data_api"
            if ok:
                result["success"] = True
                result["status_code"] = 200
                result["content"] = bd_body if use_markdown else _clean_html(bd_body)
                result["content_length"] = len(result["content"])
                result["error"] = None
            else:
                result["error"] = bd_err or result["error"]
        return result

    if _looks_like_bot_response(status, body) and BRIGHT_DATA_API_KEY:
        ok, bd_body, bd_err = _fetch_bright_data(url, use_markdown=use_markdown)
        result["method"] = "bright_data_api"
        if ok:
            result["success"] = True
            result["status_code"] = 200
            result["content"] = bd_body if use_markdown else _clean_html(bd_body)
            result["content_length"] = len(result["content"])
            result["error"] = None
        else:
            result["error"] = bd_err or f"Standard fetch returned {status}; Bright Data failed"
        return result

    if 200 <= status < 400:
        result["success"] = True
        result["content"] = _clean_html(body)
        result["content_length"] = len(result["content"])
    else:
        result["error"] = f"HTTP {status}"
    return result


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "research", "port": RESEARCH_SERVICE_PORT}), 200


@app.route("/api/research", methods=["POST"])
def research():
    """
    POST body: { "query": str, "urls": [str] }
    Returns: { success, query, total_urls, successful, failed, results: [...], summary }
    """
    payload = request.get_json(silent=True) or {}
    query = (payload.get("query") or "").strip()
    urls_raw = payload.get("urls")
    if not urls_raw:
        return jsonify({
            "success": False,
            "error": "urls is required and must be a non-empty list",
        }), 400

    urls: List[str] = []
    for u in urls_raw if isinstance(urls_raw, list) else []:
        if isinstance(u, str) and u.strip().startswith(("http://", "https://")):
            urls.append(u.strip())

    if not urls:
        return jsonify({
            "success": False,
            "error": "urls must contain at least one valid http(s) URL",
        }), 400

    # Scrape/caption/store: use Bright Data with markdown for proper article content
    prefer_bright_data = payload.get("prefer_bright_data") is True or (payload.get("format") or "").strip().lower() == "markdown"
    use_bright_data_first = _should_use_bright_data_directly(query) or prefer_bright_data
    use_markdown = prefer_bright_data and bool(BRIGHT_DATA_API_KEY)
    if use_bright_data_first:
        logger.info("Research: using Bright Data first for %s (markdown=%s)", urls, use_markdown)

    results = []
    for url in urls:
        r = _fetch_one(url, query, use_bright_data_first, use_markdown=use_markdown)
        results.append(r)

    successful = sum(1 for r in results if r["success"])
    failed = len(results) - successful
    summary = f"Successfully extracted {successful}/{len(results)} URLs"
    if failed:
        summary += f"; {failed} failed"

    return jsonify({
        "success": failed == 0,
        "query": query,
        "total_urls": len(urls),
        "successful": successful,
        "failed": failed,
        "results": results,
        "summary": summary,
    }), 200


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    app.run(host="127.0.0.1", port=RESEARCH_SERVICE_PORT, debug=False, threaded=True)


if __name__ == "__main__":
    main()
