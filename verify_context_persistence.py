#!/usr/bin/env python3
"""
Verify if Browserbase Context is actually persisting logins
Tests if the manual LinkedIn login from earlier session was saved
"""

import asyncio
import requests
from pathlib import Path
from playwright.async_api import async_playwright
from dotenv import load_dotenv
import os

load_dotenv()

BROWSERBASE_API_KEY = os.getenv("BROWSERBASE_API_KEY", "")
BROWSERBASE_PROJECT_ID = os.getenv("BROWSERBASE_PROJECT_ID", "")

async def test_context_persistence():
    context_file = Path("data/browserbase_context.txt")
    context_id = context_file.read_text().strip()
    
    print(f"Testing context persistence: {context_id}")
    print()
    
    # Create NEW session with SAME context
    response = requests.post(
        "https://api.browserbase.com/v1/sessions",
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
    
    print(f"Session ID: {session_id}")
    print(f"Live View: https://browserbase.com/sessions/{session_id}")
    print()
    
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp(connect_url)
        context = browser.contexts[0]
        page = await context.new_page()
        
        print("Navigating to LinkedIn...")
        await page.goto("https://www.linkedin.com", wait_until="networkidle", timeout=30000)
        
        await asyncio.sleep(5)
        
        title = await page.title()
        url = page.url
        
        print(f"Title: {title}")
        print(f"URL: {url}")
        print()
        
        # Check login status
        if "feed" in url.lower():
            print("✅ LOGGED IN! Context persistence works!")
            print("   You're on the LinkedIn feed")
        elif "login" in url.lower() or "sign" in title.lower():
            print("❌ NOT LOGGED IN - Context didn't persist")
            print("   Still on login page")
            print()
            print("This means:")
            print("1. The manual login from earlier wasn't saved, OR")
            print("2. The context isn't being reused properly, OR")
            print("3. LinkedIn session expired")
            print()
            print("SOLUTION: Log in again via Live View above")
            print("The session will stay open for 3 minutes...")
            await asyncio.sleep(180)
        else:
            print(f"📄 On page: {title}")
            print("   Checking if logged in...")
            
            # Try to check for logged-in indicators
            try:
                # Look for profile or feed elements
                await page.wait_for_selector('[data-test-id="feed"]', timeout=5000)
                print("✅ Found feed element - you're logged in!")
            except:
                print("⚠️  No feed element found - might not be logged in")
        
        print()
        print("Session will close in 30 seconds...")
        await asyncio.sleep(30)

if __name__ == "__main__":
    asyncio.run(test_context_persistence())
