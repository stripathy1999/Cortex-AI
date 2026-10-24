#!/usr/bin/env python3
"""
Browserbase + Playwright Integration with Persistent Context
Uses Browserbase Context API to maintain login sessions across browser tasks
"""

import os
import asyncio
import logging
import requests
from typing import Optional, Dict, Any
from playwright.async_api import async_playwright, Browser, Page
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

BROWSERBASE_API_KEY = os.getenv("BROWSERBASE_API_KEY", "")
BROWSERBASE_PROJECT_ID = os.getenv("BROWSERBASE_PROJECT_ID", "")
BROWSERBASE_API_URL = "https://www.browserbase.com/v1"


async def create_browserbase_session_with_context(context_id: str) -> Optional[Dict[str, Any]]:
    """
    Create a Browserbase session with persistent context
    
    Args:
        context_id: Context ID for persistent login state
    
    Returns:
        Dictionary with session details including connectUrl
    """
    if not BROWSERBASE_API_KEY or not BROWSERBASE_PROJECT_ID:
        logger.error("Browserbase credentials not configured")
        return None
    
    try:
        logger.info(f"Creating Browserbase session with context: {context_id}")
        
        response = requests.post(
            f"{BROWSERBASE_API_URL}/sessions",
            headers={
                "X-BB-API-Key": BROWSERBASE_API_KEY,
                "Content-Type": "application/json"
            },
            json={
                "projectId": BROWSERBASE_PROJECT_ID,
                "browserSettings": {
                    "context": {
                        "id": context_id,
                        "persist": True  # Save cookies/auth when session ends
                    }
                }
            },
            timeout=30
        )
        
        response.raise_for_status()
        data = response.json()
        
        session_info = {
            "id": data.get("id"),
            "connectUrl": data.get("connectUrl"),
            "status": data.get("status"),
            "contextId": context_id
        }
        
        logger.info(f"Created Browserbase session: {session_info['id']}")
        logger.info(f"Connect URL: {session_info['connectUrl']}")
        
        return session_info
        
    except Exception as e:
        logger.error(f"Failed to create Browserbase session: {e}")
        return None


async def execute_browser_task(instruction: str, context_id: str) -> Dict[str, Any]:
    """
    Execute a browser task using Playwright connected to Browserbase with persistent context
    
    Args:
        instruction: Natural language instruction for the task
        context_id: Context ID for persistent sessions
    
    Returns:
        Dictionary with task result
    """
    # Create Browserbase session with context
    session_info = await create_browserbase_session_with_context(context_id)
    
    if not session_info:
        return {
            "success": False,
            "message": "Failed to create Browserbase session with context"
        }
    
    session_id = session_info["id"]
    connect_url = session_info["connectUrl"]
    
    try:
        async with async_playwright() as p:
            # Connect to Browserbase session via CDP
            browser = await p.chromium.connect_over_cdp(connect_url)
            
            # Get the default context and page
            contexts = browser.contexts
            if not contexts:
                return {
                    "success": False,
                    "message": "No browser context available"
                }
            
            context = contexts[0]
            pages = context.pages
            
            if not pages:
                page = await context.new_page()
            else:
                page = pages[0]
            
            logger.info(f"Connected to Browserbase session: {session_id}")
            logger.info(f"Executing instruction: {instruction}")
            
            # Simple instruction parsing for common tasks
            instruction_lower = instruction.lower()
            
            if "go to" in instruction_lower or "navigate" in instruction_lower:
                # Extract URL from instruction
                import re
                url_match = re.search(r'(?:go to|navigate to|open)\s+([^\s]+)', instruction_lower)
                if url_match:
                    url = url_match.group(1)
                    if not url.startswith("http"):
                        url = f"https://{url}"
                    
                    logger.info(f"Navigating to: {url}")
                    await page.goto(url, wait_until="networkidle", timeout=30000)
                    
                    # Wait for page to be fully loaded
                    await page.wait_for_load_state("domcontentloaded")
                    
                    # Get page title
                    title = await page.title()
                    current_url = page.url
                    
                    result_message = f"Successfully navigated to {current_url}. Page title: {title}"
                    logger.info(result_message)
                    logger.info(f"Session will stay open for 5 minutes for manual login")
                    logger.info(f"Live View: https://browserbase.com/sessions/{session_id}")
                    
                    # Keep session open for 5 minutes to allow manual login
                    await asyncio.sleep(300)  # 5 minutes
                    
                    return {
                        "success": True,
                        "message": result_message,
                        "url": current_url,
                        "title": title,
                        "session_id": session_id,
                        "live_view": f"https://browserbase.com/sessions/{session_id}"
                    }
            
            # For other instructions, just return session info for manual interaction
            return {
                "success": True,
                "message": f"Browser session ready. Use Live View to interact: https://browserbase.com/sessions/{session_id}",
                "session_id": session_id,
                "live_view": f"https://browserbase.com/sessions/{session_id}"
            }
            
    except Exception as e:
        logger.error(f"Error executing browser task: {e}")
        return {
            "success": False,
            "message": f"Error: {str(e)}",
            "session_id": session_id,
            "live_view": f"https://browserbase.com/sessions/{session_id}"
        }
    finally:
        # Session will auto-close and save context with persist:true
        logger.info(f"Session {session_id} will save context on close")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Test with stored context
    from pathlib import Path
    context_file = Path(__file__).parent.parent / "data" / "browserbase_context.txt"
    
    if context_file.exists():
        context_id = context_file.read_text().strip()
        print(f"Testing with context: {context_id}")
        
        result = asyncio.run(execute_browser_task("go to linkedin.com", context_id))
        print(f"\nResult: {result}")
    else:
        print("❌ No context file found")
