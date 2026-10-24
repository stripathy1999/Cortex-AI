#!/usr/bin/env python3
"""
Fast Browser Automation - No AI Overhead
Direct Playwright automation for instant browser tasks
"""

import asyncio
import logging
from pathlib import Path
from playwright.async_api import async_playwright, Browser, Page
from flask import Flask, request, jsonify
from flask_cors import CORS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# Chrome user data directory for persistent sessions
CHROME_USER_DATA_DIR = Path.home() / ".cortex-chrome-data"
CHROME_USER_DATA_DIR.mkdir(exist_ok=True)

# Global browser instance
browser_instance = None
browser_context = None


async def get_browser():
    """Get or create persistent browser instance"""
    global browser_instance, browser_context
    
    if browser_instance is None:
        playwright = await async_playwright().start()
        browser_instance = await playwright.chromium.launch_persistent_context(
            user_data_dir=str(CHROME_USER_DATA_DIR),
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-sandbox",
            ],
            viewport={"width": 1920, "height": 1080},
        )
        logger.info("Browser launched")
    
    return browser_instance


async def execute_fast(instruction: str) -> dict:
    """Execute browser task instantly without AI"""
    try:
        context = await get_browser()
        
        # Get or create page
        if len(context.pages) == 0:
            page = await context.new_page()
        else:
            page = context.pages[0]
        
        instruction_lower = instruction.lower()
        
        # Simple URL navigation
        if "go to" in instruction_lower or "open" in instruction_lower or "navigate" in instruction_lower:
            # Extract URL
            import re
            url_match = re.search(r'(?:go to|open|navigate to)\s+([^\s]+)', instruction_lower)
            if url_match:
                url = url_match.group(1)
                if not url.startswith("http"):
                    url = f"https://{url}"
                
                logger.info(f"Navigating to: {url}")
                await page.goto(url, wait_until="domcontentloaded", timeout=15000)
                
                # If there's a search query
                if "search for" in instruction_lower or "search" in instruction_lower:
                    search_match = re.search(r'search (?:for )?(.+)', instruction_lower)
                    if search_match:
                        query = search_match.group(1).strip()
                        logger.info(f"Searching for: {query}")
                        
                        # Try to find search box
                        try:
                            # Common search selectors
                            search_selectors = [
                                'input[name="q"]',
                                'input[type="search"]',
                                'input[aria-label*="Search"]',
                                'textarea[name="q"]',
                            ]
                            
                            for selector in search_selectors:
                                try:
                                    await page.fill(selector, query, timeout=2000)
                                    await page.press(selector, "Enter")
                                    await page.wait_for_load_state("domcontentloaded")
                                    break
                                except:
                                    continue
                        except Exception as e:
                            logger.warning(f"Search failed: {e}")
                
                title = await page.title()
                url = page.url
                
                return {
                    "success": True,
                    "message": f"Navigated to {url}. Page: {title}",
                    "url": url,
                    "title": title
                }
        
        # Click action
        elif "click" in instruction_lower:
            text_match = re.search(r'click (?:on )?["\']?(.+?)["\']?$', instruction_lower)
            if text_match:
                text = text_match.group(1)
                await page.click(f'text="{text}"', timeout=5000)
                return {"success": True, "message": f"Clicked on '{text}'"}
        
        # Type action: focus a specific input/textarea first so we never type elsewhere
        elif "type" in instruction_lower:
            type_match = re.search(r'type ["\'](.+)["\']', instruction_lower)
            if type_match:
                text = type_match.group(1)
                # Focus first visible input or textarea so typing goes to the right place
                try:
                    inputs = page.locator("input:visible, textarea:visible")
                    if await inputs.count() > 0:
                        await inputs.first.click()
                        await asyncio.sleep(0.25)
                    await page.keyboard.type(text)
                    return {"success": True, "message": f"Typed into focused field: {text}"}
                except Exception as focus_err:
                    logger.warning(f"Focus before type failed: {focus_err}, typing to current focus")
                    await page.keyboard.type(text)
                    return {"success": True, "message": f"Typed: {text}"}
        
        return {
            "success": False,
            "message": "Could not parse instruction. Try: 'go to google.com' or 'go to google.com and search for AI news'"
        }
        
    except Exception as e:
        logger.error(f"Error: {e}")
        return {"success": False, "message": str(e)}


@app.route('/api/execute', methods=['POST'])
def execute():
    """Execute browser task endpoint"""
    data = request.json
    instruction = data.get('instruction', '')
    
    if not instruction:
        return jsonify({"success": False, "message": "No instruction provided"}), 400
    
    logger.info(f"Executing: {instruction}")
    
    # Run async function
    result = asyncio.run(execute_fast(instruction))
    
    return jsonify(result)


@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    logger.info("Fast Browser Service starting on 127.0.0.1:5009")
    app.run(host="127.0.0.1", port=5009, debug=False)
