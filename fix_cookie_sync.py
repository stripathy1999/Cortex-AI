#!/usr/bin/env python3
"""
Fixed Chrome to Browserbase Cookie Sync
Sets cookies on actual domains to ensure they work properly
"""

import os
import sqlite3
import asyncio
import requests
from pathlib import Path
from playwright.async_api import async_playwright
from dotenv import load_dotenv
from collections import defaultdict

load_dotenv()

BROWSERBASE_API_KEY = os.getenv("BROWSERBASE_API_KEY", "")
BROWSERBASE_PROJECT_ID = os.getenv("BROWSERBASE_PROJECT_ID", "")

CHROME_COOKIE_PATH = Path.home() / "Library/Application Support/Google/Chrome/Default/Cookies"


def get_chrome_cookies_by_domain():
    """Extract cookies from Chrome grouped by domain"""
    cookies_by_domain = defaultdict(list)
    
    if not CHROME_COOKIE_PATH.exists():
        print(f"❌ Chrome cookies not found at {CHROME_COOKIE_PATH}")
        return cookies_by_domain
    
    try:
        import shutil
        temp_db = Path("/tmp/chrome_cookies_temp.db")
        shutil.copy2(CHROME_COOKIE_PATH, temp_db)
        
        conn = sqlite3.connect(str(temp_db))
        cursor = conn.cursor()
        
        # Get only LinkedIn cookies for testing
        cursor.execute("""
            SELECT host_key, name, value, path, expires_utc, is_secure, is_httponly, samesite
            FROM cookies
            WHERE host_key LIKE '%linkedin%'
        """)
        
        for row in cursor.fetchall():
            host, name, value, path, expires, secure, httponly, samesite = row
            
            # Convert Chrome timestamp to Unix timestamp
            if expires:
                expires_unix = expires / 1000000 - 11644473600
            else:
                expires_unix = -1
            
            cookie = {
                "name": name,
                "value": value,
                "domain": host if host.startswith('.') else f".{host}",
                "path": path,
                "expires": expires_unix,
                "secure": bool(secure),
                "httpOnly": bool(httponly),
                "sameSite": ["None", "Lax", "Strict"][samesite] if samesite in [0, 1, 2] else "Lax"
            }
            
            # Group by base domain
            base_domain = host.replace('.', '')
            cookies_by_domain[base_domain].append(cookie)
        
        conn.close()
        temp_db.unlink()
        
        print(f"✅ Found {sum(len(c) for c in cookies_by_domain.values())} LinkedIn cookies")
        
    except Exception as e:
        print(f"❌ Failed to read Chrome cookies: {e}")
    
    return cookies_by_domain


async def sync_cookies_to_browserbase(context_id: str):
    """Sync cookies to Browserbase by visiting domains and setting cookies"""
    
    cookies_by_domain = get_chrome_cookies_by_domain()
    
    if not cookies_by_domain:
        print("❌ No cookies to sync")
        return
    
    # Create Browserbase session with context
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
    
    print(f"✅ Created session: {session_id}")
    
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp(connect_url)
        context = browser.contexts[0]
        page = await context.new_page()
        
        # Visit LinkedIn first to set cookies on the right domain
        print("📍 Visiting linkedin.com...")
        await page.goto("https://www.linkedin.com", wait_until="domcontentloaded")
        
        # Add LinkedIn cookies
        linkedin_cookies = []
        for domain, cookies in cookies_by_domain.items():
            if 'linkedin' in domain:
                linkedin_cookies.extend(cookies)
        
        if linkedin_cookies:
            print(f"🍪 Adding {len(linkedin_cookies)} LinkedIn cookies...")
            await context.add_cookies(linkedin_cookies)
            print("✅ Cookies added")
        
        # Reload to apply cookies
        print("🔄 Reloading page with cookies...")
        await page.reload(wait_until="domcontentloaded")
        await asyncio.sleep(3)
        
        title = await page.title()
        url = page.url
        
        print(f"📄 Title: {title}")
        print(f"🔗 URL: {url}")
        
        if "feed" in url or "Feed" in title:
            print("✅ SUCCESS! Logged in to LinkedIn!")
        else:
            print("⚠️  Still on login page - cookies may need manual login")
        
        print(f"🌐 Live View: https://browserbase.com/sessions/{session_id}")
        print("⏳ Keeping session open for 2 minutes...")
        await asyncio.sleep(120)


async def main():
    context_file = Path("data/browserbase_context.txt")
    context_id = context_file.read_text().strip()
    
    print(f"🔄 Syncing Chrome cookies to Browserbase Context: {context_id}")
    print()
    
    await sync_cookies_to_browserbase(context_id)
    
    print()
    print("✅ Done! Context will be saved with persist:true")


if __name__ == "__main__":
    asyncio.run(main())
