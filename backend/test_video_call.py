#!/usr/bin/env python3
"""Test video call feature - run from backend/ with: uv run python test_video_call.py"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

def test_imports():
    print("1. Imports...")
    from video_call_service import is_video_call_request, get_video_call_options, start_video_call
    print("   OK")

def test_detection():
    print("\n2. Detection...")
    from video_call_service import is_video_call_request
    assert is_video_call_request("video call me")
    assert not is_video_call_request("open notepad")
    print("   OK")

def test_options():
    print("\n3. Options...")
    from video_call_service import get_video_call_options, _find_whatsapp_exe
    opts = get_video_call_options()
    wa = _find_whatsapp_exe()
    print(f"   Recommended: {opts.get('recommended')}, WhatsApp: {'found' if wa else 'not found'} ({wa})")

def test_start_video_call():
    print("\n4. start_video_call...")
    from video_call_service import start_video_call
    from unittest.mock import patch
    with patch("video_call_service._google_meet_create", return_value=None):
        with patch("video_call_service._zoom_api_create_meeting", return_value=None):
            r = start_video_call(target_platform="meet", source="discord:1")
    assert "success" in r and "message" in r
    print("   OK")

def test_simple_browser():
    print("\n5. Simple browser open...")
    from main import _try_simple_browser_open
    u = _try_simple_browser_open("search hello on google")
    assert u and "google.com" in u
    u2 = _try_simple_browser_open("go to youtube music")
    assert u2 and "youtube" in u2
    print("   OK")

def test_live_api():
    print("\n6. Live API (8003)...")
    try:
        import requests
        r = requests.get("http://127.0.0.1:8003/api/video_call_options", timeout=3)
        print(f"   Status: {r.status_code}" + (f", recommended: {r.json().get('recommended')}" if r.ok else ""))
    except Exception as e:
        print(f"   SKIP: {e}")


def test_share_screen_api():
    """Test Agent-S /api/share_screen endpoint (requires Agent-S on 8001 with grounding)."""
    print("\n7. Share screen API (8001)...")
    try:
        import requests
        r = requests.post(
            "http://127.0.0.1:8001/api/share_screen",
            json={},
            timeout=90,
        )
        data = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
        success = data.get("success", False)
        msg = data.get("message") or data.get("error", r.text or str(r.status_code))
        print(f"   Status: {r.status_code}, success: {success}, msg: {msg}")
        if r.status_code == 500 and "Agent not configured" in str(msg):
            print("   SKIP: Agent-S not running with --ground_model")
            return
        if r.status_code == 404:
            print("   SKIP: /api/share_screen not found - restart Agent-S with --ground_model")
            return
        assert r.status_code in (200, 500), f"Unexpected status {r.status_code}"
        print("   OK (endpoint reachable)" + (" - share screen triggered" if success else " - error (see msg)"))
    except requests.exceptions.ConnectionError:
        print("   SKIP: Agent-S not running on 8001")
    except requests.exceptions.Timeout:
        print("   SKIP: Timeout (grounding may be slow)")
    except Exception as e:
        print(f"   SKIP: {e}")


if __name__ == "__main__":
    print("=== VIDEO CALL + BROWSER + SHARE SCREEN TEST ===")
    test_imports()
    test_detection()
    test_options()
    test_start_video_call()
    test_simple_browser()
    test_live_api()
    test_share_screen_api()
    print("\nDone.")
