#!/usr/bin/env python3
"""Test Bright Data Web Unlocker API"""

import os
import requests
from dotenv import load_dotenv

load_dotenv()

BRIGHT_DATA_API_KEY = os.getenv("BRIGHT_DATA_API_KEY", "")
BRIGHT_DATA_ZONE = os.getenv("BRIGHT_DATA_ZONE", "web_unlocker2")

def test_brightdata_api(url: str):
    """Test Bright Data Web Unlocker with a URL"""
    
    print(f"Testing Bright Data Web Unlocker")
    print(f"URL: {url}")
    print(f"Zone: {BRIGHT_DATA_ZONE}")
    print()
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {BRIGHT_DATA_API_KEY}"
    }
    
    payload = {
        "zone": BRIGHT_DATA_ZONE,
        "url": url,
        "format": "raw"
    }
    
    print("Sending request to Bright Data API...")
    
    try:
        response = requests.post(
            "https://api.brightdata.com/request",
            headers=headers,
            json=payload,
            timeout=60
        )
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            content = response.text
            print(f"✅ SUCCESS! Retrieved {len(content)} characters")
            print()
            print("First 500 characters:")
            print("-" * 50)
            print(content[:500])
            print("-" * 50)
            return True
        else:
            print(f"❌ FAILED: {response.status_code}")
            print(f"Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("BRIGHT DATA WEB UNLOCKER TEST")
    print("=" * 60)
    print()
    
    # Test 1: Simple site (should work with standard fetch too)
    print("TEST 1: Simple site (example.com)")
    print("-" * 60)
    test_brightdata_api("https://example.com")
    print()
    
    # Test 2: Bot-protected site (needs Bright Data)
    print("TEST 2: Bot-protected site (nowsecure.nl)")
    print("-" * 60)
    test_brightdata_api("https://nowsecure.nl")
    print()
    
    # Test 3: LinkedIn (requires login but should at least load)
    print("TEST 3: LinkedIn (public page)")
    print("-" * 60)
    test_brightdata_api("https://www.linkedin.com")
    print()
    
    print("=" * 60)
    print("Tests complete!")
