#!/usr/bin/env python3
"""
Create a Browserbase Context and save its ID for persistent logins.
Run this once, then run sync_chrome_to_browserbase.py to copy your Chrome cookies.
"""

import os
import sys
import requests
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root
env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

BROWSERBASE_API_KEY = os.getenv("BROWSERBASE_API_KEY", "")
BROWSERBASE_PROJECT_ID = os.getenv("BROWSERBASE_PROJECT_ID", "")
CONTEXTS_API_URL = "https://api.browserbase.com/v1/contexts"


def create_context() -> str | None:
    """Create a new Browserbase context. Returns context ID or None."""
    if not BROWSERBASE_API_KEY or not BROWSERBASE_PROJECT_ID:
        print("❌ Set BROWSERBASE_API_KEY and BROWSERBASE_PROJECT_ID in .env")
        return None

    try:
        response = requests.post(
            CONTEXTS_API_URL,
            headers={
                "X-BB-API-Key": BROWSERBASE_API_KEY,
                "Content-Type": "application/json",
            },
            json={"projectId": BROWSERBASE_PROJECT_ID},
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        context_id = data.get("id")
        if not context_id:
            print("❌ No context ID in response")
            return None
        return context_id
    except requests.RequestException as e:
        print(f"❌ Failed to create context: {e}")
        if hasattr(e, "response") and e.response is not None:
            try:
                err = e.response.json()
                print(f"   {err}")
            except Exception:
                print(f"   {e.response.text[:200]}")
        return None


def main():
    print("🔄 Creating Browserbase context...")
    context_id = create_context()
    if not context_id:
        sys.exit(1)

    # Save to data/browserbase_context.txt
    data_dir = Path(__file__).resolve().parent.parent / "data"
    data_dir.mkdir(exist_ok=True)
    context_file = data_dir / "browserbase_context.txt"
    context_file.write_text(context_id.strip(), encoding="utf-8")
    print(f"✅ Context created: {context_id}")
    print(f"   Saved to: {context_file}")
    print()
    print("Next steps:")
    print("  1. Close Chrome (optional but recommended for cookie copy)")
    print("  2. Run: python sync_chrome_to_browserbase.py")
    print("  3. Add BROWSERBASE_CONTEXT_ID=" + context_id + " to .env (or leave empty to use file)")
    print()
    print("🎉 Stagehand + Browserbase will now use your Chrome credentials!")


if __name__ == "__main__":
    main()
