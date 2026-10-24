#!/usr/bin/env python3
"""
Browserbase Session Manager with Context Support
Creates browser sessions with persistent context for login state
"""

import os
import logging
import requests
from typing import Optional, Dict, Any
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)

BROWSERBASE_API_KEY = os.getenv("BROWSERBASE_API_KEY", "")
BROWSERBASE_PROJECT_ID = os.getenv("BROWSERBASE_PROJECT_ID", "")
BROWSERBASE_API_URL = "https://api.browserbase.com/v1"


def create_session_with_context(context_id: str) -> Optional[Dict[str, Any]]:
    """
    Create a Browserbase session with persistent context
    
    Args:
        context_id: Context ID to use for persistent login state
    
    Returns:
        Dictionary with session details including connectUrl, or None if failed
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
                    "context": {"id": context_id, "persist": True}
                },
                "keepAlive": True
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
        
        logger.info(f"Created session: {session_info['id']}")
        logger.info(f"Connect URL: {session_info['connectUrl']}")
        
        return session_info
        
    except Exception as e:
        logger.error(f"Failed to create Browserbase session: {e}")
        return None


def get_session_status(session_id: str) -> Optional[Dict[str, Any]]:
    """Get status of a Browserbase session"""
    if not BROWSERBASE_API_KEY:
        return None
    
    try:
        response = requests.get(
            f"{BROWSERBASE_API_URL}/sessions/{session_id}",
            headers={"X-BB-API-Key": BROWSERBASE_API_KEY},
            timeout=10
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Failed to get session status: {e}")
        return None


def end_session(session_id: str) -> bool:
    """End a Browserbase session"""
    if not BROWSERBASE_API_KEY:
        return False
    
    try:
        response = requests.post(
            f"{BROWSERBASE_API_URL}/sessions/{session_id}",
            headers={"X-BB-API-Key": BROWSERBASE_API_KEY, "Content-Type": "application/json"},
            json={"projectId": BROWSERBASE_PROJECT_ID, "status": "REQUEST_RELEASE"},
            timeout=10,
        )
        response.raise_for_status()
        logger.info(f"Ended session: {session_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to end session: {e}")
        return False


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Test with stored context
    from pathlib import Path
    context_file = Path(__file__).parent.parent / "data" / "browserbase_context.txt"
    
    if context_file.exists():
        context_id = context_file.read_text().strip()
        print(f"Testing with context: {context_id}")
        
        session = create_session_with_context(context_id)
        if session:
            print(f"✅ Session created: {session['id']}")
            print(f"   Connect URL: {session['connectUrl']}")
            print(f"   Status: {session['status']}")
            print(f"\nYou can connect to this session via CDP or view it in Browserbase dashboard")
        else:
            print("❌ Failed to create session")
    else:
        print("❌ No context file found")
