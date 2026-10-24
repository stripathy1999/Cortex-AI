#!/usr/bin/env python3
"""Quick test of Browserbase Context with synced cookies"""

import asyncio
import requests
from pathlib import Path
from playwright.async_api import async_playwright
from dotenv import load_dotenv
import os

load_dotenv()

BROWSERBASE_API_KEY = os.getenv("BROWSERBASE_API_KEY", "")
BROWSERBASE_PROJECT_ID = os.getenv("BROWSERBASE_PROJECT_ID", "")

async def test_linkedin_login():
    # Get context ID
    context_file = Path("data/browserbase_context.txt")
    context_id = context_file.read_text().strip()
    
    print(f"Testing with context: {context_id}")
    
    # Create session with context
    response = requests.post(
        "https://www.browserbase.com/v1/sessions",
        headers={
            "X-BB-API-Key": BROWSERBASE_API_KEY,
            "Content-Type": "application/json"
        },
        json={
            "projectId": BROWSERBASE_PROJECT_ID,
            "browserSettings": {
                "context": {
                    "id": context_id,
                    "persist": True
                }
            }
        },
        timeout=30
    )
    
    session_data = response.json()
    session_id = session_data["id"]
    connect_url = session_data["connectUrl"]
    
    print(f"Session: {session_id}")
    print(f"Live View: https://browserbase.com/sessions/{session_id}")
    
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp(connect_url)
        context = browser.contexts[0]
        
        if not context.pages:
            page = await context.new_page()
        else:
            page = context.pages[0]
        
        print("Navigating to LinkedIn...")
        await page.goto("https://www.linkedin.com", wait_until="domcontentloaded", timeout=30000)
        
        await asyncio.sleep(3)
        
        title = await page.title()
        url = page.url
        
        print(f"Title: {title}")
        print(f"URL: {url}")
        
        # Check if logged in
        if "feed" in url or "Feed" in title:
            print("✅ LOGGED IN! Cookies worked!")
        elif "login" in url.lower() or "sign in" in title.lower():
            print("⚠️  Not logged in - on login page")
        else:
            print(f"📄 On page: {title}")
        
        print("\nSession will stay open for 30 seconds...")
        await asyncio.sleep(30)

if __name__ == "__main__":
    asyncio.run(test_linkedin_login())
