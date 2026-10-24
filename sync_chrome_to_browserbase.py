#!/usr/bin/env python3
"""
Sync Chrome Cookies to Browserbase Context
Copies all cookies from your Chrome browser to Browserbase Context for persistent logins.
On macOS, decrypts encrypted_value for auth cookies (LinkedIn, Gmail, etc.).
Run: cd backend && uv run python ../sync_chrome_to_browserbase.py
     (or: python3 sync_chrome_to_browserbase.py from project root - decryption needs pycryptodome)
"""

import os
import sqlite3
import asyncio
import shutil
import subprocess
import sys
import time
import uuid
import requests
from pathlib import Path
from playwright.async_api import async_playwright
from dotenv import load_dotenv


# Load .env from project root
ENV_PATH = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=ENV_PATH)

BROWSERBASE_API_KEY = os.getenv("BROWSERBASE_API_KEY", "")
BROWSERBASE_PROJECT_ID = os.getenv("BROWSERBASE_PROJECT_ID", "")
BROWSERBASE_API_URL = "https://api.browserbase.com/v1"
MAX_RETRIES = 3
RETRY_DELAY = 2

# Chrome cookie paths (Default + Profile 1/2/3) — Default first for priority
CHROME_BASE = Path.home() / "Library/Application Support/Google/Chrome"
CHROME_COOKIE_PATHS = [
    CHROME_BASE / "Default/Cookies",
    CHROME_BASE / "Profile 1/Cookies",
    CHROME_BASE / "Profile 2/Cookies",
    CHROME_BASE / "Profile 3/Cookies",
]


def _dedupe_cookies(cookies: list) -> list:
    """Deduplicate by (domain, name), keeping the one with the latest expiry."""
    seen: dict[tuple[str, str], dict] = {}
    for c in cookies:
        key = (c["domain"], c["name"])
        if key not in seen or (c.get("expires", 0) or 0) > (seen[key].get("expires", 0) or 0):
            seen[key] = c
    return list(seen.values())


def _decrypt_chrome_value(encrypted_blob: bytes) -> str | None:
    """Decrypt Chrome encrypted_value (v10/v11) on macOS. Returns plaintext or None."""
    if not encrypted_blob or len(encrypted_blob) < 15:
        return None
    try:
        from Crypto.Cipher import AES
        from Crypto.Protocol.KDF import PBKDF2
    except ImportError:
        return None
    # Get Chrome Safe Storage key from Keychain (macOS only)
    try:
        result = subprocess.run(
            ["security", "find-generic-password", "-w", "-a", "Chrome Safe Storage", "-s", "Chrome Safe Storage"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0 or not result.stdout.strip():
            return None
        password = result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return None
    try:
        key = PBKDF2(password.encode("utf8"), b"saltysalt", 16, 1003)
        iv = b" " * 16
        if encrypted_blob[:3] in (b"v10", b"v11"):
            cipher = AES.new(key, AES.MODE_CBC, iv)
            decrypted = cipher.decrypt(encrypted_blob[3:])
            # Remove PKCS7 padding
            pad = decrypted[-1]
            if isinstance(pad, int) and 0 < pad <= 16:
                decrypted = decrypted[:-pad]
            return decrypted.decode("utf-8", errors="replace").rstrip("\x00")
    except Exception:
        pass
    return None


def get_chrome_cookies() -> list:
    """Extract cookies from Chrome database."""
    all_cookies: list[dict] = []

    for cookie_path in CHROME_COOKIE_PATHS:
        if not cookie_path.exists():
            continue

        try:
            temp_db = Path(f"/tmp/chrome_cookies_{uuid.uuid4().hex[:8]}.db")
            shutil.copy2(cookie_path, temp_db)
            
            conn = sqlite3.connect(str(temp_db))
            cursor = conn.cursor()
            
            # Read value and encrypted_value (Chrome encrypts auth cookies on macOS)
            cursor.execute("""
                SELECT host_key, name, value, encrypted_value, path, expires_utc, is_secure, is_httponly, samesite
                FROM cookies
            """)
            decrypted_count = 0
            for row in cursor.fetchall():
                host, name, value, encrypted_value, path, expires, secure, httponly, samesite = row
                cookie_value = value or ""
                # If value empty but encrypted_value exists, decrypt (LinkedIn, etc.)
                if not cookie_value and encrypted_value and sys.platform == "darwin":
                    dec = _decrypt_chrome_value(encrypted_value)
                    if dec:
                        cookie_value = dec
                        decrypted_count += 1
                all_cookies.append({
                    "name": name,
                    "value": cookie_value,
                    "domain": host,
                    "path": path or "/",
                    "expires": expires / 1000000 - 11644473600 if expires and expires > 0 else -1,
                    "secure": bool(secure),
                    "httpOnly": bool(httponly),
                    "sameSite": ["None", "Lax", "Strict"][samesite] if samesite in [0, 1, 2] else "None",
                })
            if decrypted_count:
                print(f"   Decrypted {decrypted_count} auth cookies")

            conn.close()
            try:
                temp_db.unlink()
            except OSError:
                pass

            print(f"✅ Extracted from {cookie_path.name}")
            
        except Exception as e:
            print(f"⚠️  Failed to read {cookie_path}: {e}")

    return _dedupe_cookies(all_cookies)


def _api_post(url: str, json_data: dict, retries: int = MAX_RETRIES) -> dict:
    """POST with retries for transient failures."""
    headers = {
        "X-BB-API-Key": BROWSERBASE_API_KEY,
        "Content-Type": "application/json",
    }
    for attempt in range(retries):
        try:
            r = requests.post(url, headers=headers, json=json_data, timeout=60)
            r.raise_for_status()
            return r.json()
        except requests.RequestException as e:
            if attempt < retries - 1:
                time.sleep(RETRY_DELAY)
                continue
            raise


def _end_session(session_id: str, retries: int = MAX_RETRIES) -> None:
    """End Browserbase session via Update API (REQUEST_RELEASE)."""
    url = f"{BROWSERBASE_API_URL}/sessions/{session_id}"
    headers = {"X-BB-API-Key": BROWSERBASE_API_KEY, "Content-Type": "application/json"}
    body = {"projectId": BROWSERBASE_PROJECT_ID, "status": "REQUEST_RELEASE"}
    for attempt in range(retries):
        try:
            r = requests.post(url, headers=headers, json=body, timeout=30)
            r.raise_for_status()
            return
        except requests.RequestException as e:
            if attempt < retries - 1:
                time.sleep(RETRY_DELAY)
                continue
            raise


async def upload_cookies_to_browserbase(context_id: str, cookies: list) -> None:
    """Upload cookies to Browserbase Context via Playwright, then end session cleanly."""
    session_data = _api_post(
        f"{BROWSERBASE_API_URL}/sessions",
        {
            "projectId": BROWSERBASE_PROJECT_ID,
            "browserSettings": {
                "context": {"id": context_id, "persist": True},
            },
        },
    )
    session_id = session_data["id"]
    connect_url = session_data["connectUrl"]
    print(f"✅ Created Browserbase session: {session_id}")

    try:
        async with async_playwright() as p:
            browser = await p.chromium.connect_over_cdp(connect_url)
            ctx = browser.contexts[0]

            await ctx.add_cookies(cookies)
            print(f"✅ Uploaded {len(cookies)} cookies to Browserbase Context")

            await asyncio.sleep(3)  # Let cookies settle before closing
    finally:
        try:
            _end_session(session_id)
            print("✅ Session ended, context saved")
            # Browserbase: wait before reusing context so data is synchronized
            import time
            time.sleep(8)
            print("   (Context synced. Safe to run tasks.)")
        except Exception as e:
            print(f"⚠️  Session end failed (context may still be saved): {e}")


def _get_or_create_context() -> str | None:
    """Get context ID from file, or create one if missing."""
    context_file = Path(__file__).parent / "data" / "browserbase_context.txt"
    if context_file.exists():
        return context_file.read_text().strip()

    # Create context via API
    print("📦 No context found. Creating Browserbase context...")
    try:
        resp = requests.post(
            "https://api.browserbase.com/v1/contexts",
            headers={
                "X-BB-API-Key": BROWSERBASE_API_KEY,
                "Content-Type": "application/json",
            },
            json={"projectId": BROWSERBASE_PROJECT_ID},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        context_id = data.get("id")
        if context_id:
            context_file.parent.mkdir(parents=True, exist_ok=True)
            context_file.write_text(context_id.strip(), encoding="utf-8")
            print(f"✅ Created context: {context_id}")
            return context_id
    except Exception as e:
        print(f"❌ Failed to create context: {e}")
    return None


async def main():
    print("🔄 Syncing Chrome cookies to Browserbase Context...")
    print()

    # Get or create context ID
    context_id = _get_or_create_context()
    if not context_id:
        print("❌ No Browserbase context. Set BROWSERBASE_API_KEY and BROWSERBASE_PROJECT_ID in .env.")
        return

    print(f"📋 Context ID: {context_id}")
    print()
    
    # Extract Chrome cookies
    print("📂 Extracting cookies from Chrome...")
    cookies = get_chrome_cookies()
    
    if not cookies:
        print("❌ No cookies found in Chrome")
        return
    
    print(f"✅ Found {len(cookies)} total cookies")
    print()
    
    # Upload to Browserbase
    print("☁️  Uploading cookies to Browserbase Context...")
    await upload_cookies_to_browserbase(context_id, cookies)
    
    print()
    print("✅ Cookie sync complete!")
    print()
    print("🎉 All your Chrome logins are now available in Browserbase!")
    print("   Future browser tasks will use these cookies automatically.")


if __name__ == "__main__":
    asyncio.run(main())
