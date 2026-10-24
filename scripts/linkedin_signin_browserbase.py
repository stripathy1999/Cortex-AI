#!/usr/bin/env python3
"""
Open a Browserbase session and go to LinkedIn sign-in.
Use Live View to sign in (with Google or email); the session is persisted.

Run from project root:
  cd backend && uv run python ../scripts/linkedin_signin_browserbase.py
"""

import asyncio
import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv
from playwright.async_api import async_playwright

# Project root and .env
ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

BROWSERBASE_API_KEY = os.getenv("BROWSERBASE_API_KEY", "")
BROWSERBASE_PROJECT_ID = os.getenv("BROWSERBASE_PROJECT_ID", "")
BROWSERBASE_API_URL = "https://api.browserbase.com/v1"
CONTEXT_FILE = ROOT / "data" / "browserbase_context.txt"
KEEP_OPEN_SECONDS = int(os.getenv("LINKEDIN_SIGNIN_KEEP_OPEN", "300"))  # 5 min


def get_context_id() -> str | None:
    if os.getenv("BROWSERBASE_CONTEXT_ID", "").strip():
        return os.getenv("BROWSERBASE_CONTEXT_ID", "").strip()
    if CONTEXT_FILE.exists():
        return CONTEXT_FILE.read_text().strip()
    return None


def create_session(context_id: str) -> dict | None:
    resp = requests.post(
        f"{BROWSERBASE_API_URL}/sessions",
        headers={"X-BB-API-Key": BROWSERBASE_API_KEY, "Content-Type": "application/json"},
        json={
            "projectId": BROWSERBASE_PROJECT_ID,
            "browserSettings": {
                "context": {"id": context_id, "persist": True},
            },
            "keepAlive": True,
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def end_session(session_id: str) -> None:
    requests.post(
        f"{BROWSERBASE_API_URL}/sessions/{session_id}",
        headers={"X-BB-API-Key": BROWSERBASE_API_KEY, "Content-Type": "application/json"},
        json={"projectId": BROWSERBASE_PROJECT_ID, "status": "REQUEST_RELEASE"},
        timeout=15,
    )


async def main():
    if not BROWSERBASE_API_KEY or not BROWSERBASE_PROJECT_ID:
        print("❌ Set BROWSERBASE_API_KEY and BROWSERBASE_PROJECT_ID in .env")
        sys.exit(1)

    context_id = get_context_id()
    if not context_id:
        print("❌ No Browserbase context. Run sync first: cd backend && uv run python ../sync_chrome_to_browserbase.py")
        sys.exit(1)

    print("🔐 Opening Browserbase session for LinkedIn sign-in...")
    data = create_session(context_id)
    session_id = data["id"]
    connect_url = data["connectUrl"]
    live_view = f"https://browserbase.com/sessions/{session_id}"

    print()
    print("   👉 Open this link and sign in to LinkedIn (use Sign in with Google if you prefer):")
    print(f"   {live_view}")
    print()
    print("   Session stays open for", KEEP_OPEN_SECONDS // 60, "minutes. Your login will be saved.")
    print()

    try:
        async with async_playwright() as p:
            browser = await p.chromium.connect_over_cdp(connect_url)
            ctx = browser.contexts[0]
            page = ctx.pages[0] if ctx.pages else await ctx.new_page()
            await page.goto("https://www.linkedin.com/login", wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(KEEP_OPEN_SECONDS)
    finally:
        try:
            end_session(session_id)
            print("✅ Session ended. LinkedIn login saved to context.")
            import time
            time.sleep(8)  # Let Browserbase sync context before reuse
        except Exception as e:
            print(f"⚠️  Session end failed (context may still be saved): {e}")


if __name__ == "__main__":
    asyncio.run(main())
