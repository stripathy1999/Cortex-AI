"""
Video call service: intelligently choose Zoom, Google Meet, or WhatsApp
to video call the user and optionally share screen.

Checks availability in order:
1. Zoom - if installed and API credentials configured
2. Google Meet - always available via browser
3. WhatsApp - if Desktop installed and user number known
"""

from __future__ import annotations

import base64
import json
import logging
import os
import platform
import re
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests

logger = logging.getLogger(__name__)

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
if ENV_PATH.exists():
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=ENV_PATH)

# Zoom API (Server-to-Server OAuth)
ZOOM_ACCOUNT_ID = os.getenv("ZOOM_ACCOUNT_ID", "").strip()
ZOOM_CLIENT_ID = os.getenv("ZOOM_CLIENT_ID", "").strip()
ZOOM_CLIENT_SECRET = os.getenv("ZOOM_CLIENT_SECRET", "").strip()

# Stagehand for Google Meet
STAGEHAND_SERVICE_URL = os.getenv("STAGEHAND_SERVICE_URL", "http://127.0.0.1:5005")

# FaceTime: default country code when number has no country code (e.g. 9871172037 -> 919871172037)
FACETIME_DEFAULT_COUNTRY_CODE = (os.getenv("FACETIME_DEFAULT_COUNTRY_CODE") or "").strip()
# FaceTime: always call this number when user says "FaceTime me" (e.g. +15555550100)
FACETIME_DEFAULT_NUMBER = (os.getenv("FACETIME_DEFAULT_NUMBER") or "").strip()
# FaceTime: your Apple ID for FaceTime on Mac (sign in on Mac with this; used as fallback if no number)
FACETIME_APPLE_ID = (os.getenv("FACETIME_APPLE_ID") or "").strip()
# FaceTime: seconds to wait after opening facetime:// before clicking Call (default 10; increase if FaceTime loads slowly)
try:
    FACETIME_CALL_DELAY_SEC = float(os.getenv("FACETIME_CALL_DELAY_SEC", "10").strip() or "10")
except ValueError:
    FACETIME_CALL_DELAY_SEC = 10.0
# Agent-S URL for vision-based FaceTime button click (Claude/grounding). If Agent-S is running, we try this first.
AGENT_HOST = os.getenv("AGENT_HOST", "127.0.0.1").strip() or "127.0.0.1"
AGENT_PORT = os.getenv("AGENT_PORT", "8005").strip() or "8005"
AGENT_S_BASE_URL = f"http://{AGENT_HOST}:{AGENT_PORT}"

# Common Zoom install paths on Windows
ZOOM_PATHS_WIN = [
    Path(os.environ.get("PROGRAMFILES", "C:\\Program Files")) / "Zoom" / "bin" / "Zoom.exe",
    Path(os.environ.get("PROGRAMFILES(X86)", "C:\\Program Files (x86)")) / "Zoom" / "bin" / "Zoom.exe",
    Path(os.environ.get("LOCALAPPDATA", "")) / "Zoom" / "bin" / "Zoom.exe",
]

# WhatsApp Desktop paths
WHATSAPP_PATHS_WIN = [
    Path(os.environ.get("LOCALAPPDATA", "")) / "WhatsApp" / "WhatsApp.exe",
    Path(os.environ.get("PROGRAMFILES", "C:\\Program Files")) / "WhatsApp" / "WhatsApp.exe",
]


def _is_windows() -> bool:
    return platform.system().lower() == "windows"


def _is_darwin() -> bool:
    return platform.system() == "Darwin"


def _find_zoom_exe() -> Optional[Path]:
    """Check if Zoom is installed."""
    if not _is_windows():
        return None
    for p in ZOOM_PATHS_WIN:
        if p and p.exists():
            return p
    # Fallback: check PATH
    try:
        result = subprocess.run(
            ["where", "Zoom"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            return Path(result.stdout.strip().splitlines()[0].strip())
    except Exception:
        pass
    return None


def _find_whatsapp_exe() -> Optional[Path]:
    """Check if WhatsApp Desktop is installed (installer or Microsoft Store)."""
    if not _is_windows():
        return None
    for p in WHATSAPP_PATHS_WIN:
        if p and p.exists():
            return p
    # Microsoft Store: WindowsApps folder (version in path varies)
    try:
        winapps = Path(os.environ.get("PROGRAMFILES", "C:\\Program Files")) / "WindowsApps"
        if winapps.exists():
            for d in winapps.iterdir():
                if d.is_dir() and "WhatsApp" in d.name and "Desktop" in d.name:
                    exe = d / "WhatsApp.exe"
                    if exe.exists():
                        return exe
    except (PermissionError, OSError):
        pass
    # App execution alias (Microsoft Store)
    try:
        localappdata = os.environ.get("LOCALAPPDATA", "")
        alias = Path(localappdata) / "Microsoft" / "WindowsApps" / "WhatsApp.exe"
        if alias.exists():
            return alias
    except Exception:
        pass
    try:
        result = subprocess.run(
            ["where", "WhatsApp"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            return Path(result.stdout.strip().splitlines()[0].strip())
    except Exception:
        pass
    return None


def _normalize_facetime_contact(phone_or_email: str) -> Optional[str]:
    """
    Normalize contact for facetime:// URL.
    - Email: use as-is (e.g. user@example.com).
    - Phone: digits only with country code (e.g. +91 9871... -> 919871172037).
      Apple expects digits only, no '+' or spaces.
    """
    raw = str(phone_or_email).strip()
    # Strip iMessage/SMS handle prefix if present (e.g. "iMessage;-;+919871172037")
    for prefix in ("iMessage;-;", "iMessage;+;", "sms;-;", "sms;+;"):
        if raw.lower().startswith(prefix.lower()):
            raw = raw[len(prefix) :].strip()
            break
    raw = re.sub(r"\s", "", raw)
    if not raw:
        return None
    if "@" in raw:
        return raw
    # Phone: digits only (Apple facetime:// expects e.g. 14085551234, no +)
    digits = re.sub(r"\D", "", raw)
    if not digits:
        return None
    # If 10-digit, prepend country code so FaceTime rings the right device
    if len(digits) == 10:
        code = re.sub(r"\D", "", (FACETIME_DEFAULT_COUNTRY_CODE or "").strip())
        if code:
            digits = code + digits
        else:
            # Default US (1) when no FACETIME_DEFAULT_COUNTRY_CODE set
            digits = "1" + digits
    return digits


def _facetime_click_call_button() -> bool:
    """
    After FaceTime is open, activate it and press Return or click the Call/Video button.
    Requires: System Preferences > Privacy & Security > Accessibility > Terminal (or your app) allowed.
    """
    if not _is_darwin():
        logger.warning("FaceTime: not macOS, skipping click")
        return False
    # Caller may run this after a delay; still give the window a moment
    time.sleep(2)
    activate_script = 'tell application "FaceTime" to activate'
    try:
        subprocess.run(["osascript", "-e", activate_script], capture_output=True, timeout=5)
    except Exception as e:
        logger.warning("FaceTime activate failed: %s", e)
    time.sleep(1.5)

    def run_applescript(script: str) -> Tuple[bool, str]:
        try:
            ret = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True,
                text=True,
                timeout=10,
            )
            return ret.returncode == 0, (ret.stderr or "").strip()
        except Exception as e:
            return False, str(e)

    # 1) Click the "Call" button by exact title first (bottom of window, next to Cancel/mic/video)
    call_script = """
    tell application "System Events"
        if not (exists process "FaceTime") then return false
        set ft to process "FaceTime"
        set frontmost of ft to true
        delay 0.5
        if exists window 1 of ft then
            set w to window 1 of ft
            set n to count of buttons of w
            repeat with i from 1 to n
                try
                    set b to button i of w
                    set t to (value of attribute "AXTitle" of b) as text
                    if t is "Call" then
                        click b
                        return true
                    end if
                end try
                try
                    set d to (value of attribute "AXDescription" of b) as text
                    if d contains "Call" and d does not contain "Cancel" then
                        click b
                        return true
                    end if
                end try
            end repeat
            try
                if exists (button "Call" of w) then
                    click button "Call" of w
                    return true
                end if
            end try
        end if
    end tell
    return false
    """
    ok, err = run_applescript(call_script)
    if ok:
        logger.info("FaceTime: clicked Call button (by title)")
        return True
    time.sleep(0.5)

    # 2) Try Return (default button often starts the call)
    for attempt in range(3):
        ok, err = run_applescript(
            'tell application "System Events" to tell process "FaceTime" to key code 36'
        )
        if ok:
            logger.info("FaceTime: sent Return (start call)")
            return True
        time.sleep(0.8)
    # 3) Try Cmd+Return (some dialogs use this for primary action)
    ok, _ = run_applescript(
        'tell application "System Events" to tell process "FaceTime" to keystroke return using command down'
    )
    if ok:
        logger.info("FaceTime: sent Cmd+Return")
        return True
    time.sleep(0.5)

    # 4) Use accessibility (AXPress) to press the default or primary button – works like Apple Vision / VoiceOver
    axpress_script = """
    tell application "System Events"
        if not (exists process "FaceTime") then return
        set ft to process "FaceTime"
        set frontmost of ft to true
        delay 0.5
        if exists window 1 of ft then
            set w to window 1 of ft
            try
                set n to count of buttons of w
                repeat with i from 1 to n
                    try
                        set b to button i of w
                        set btnName to (value of attribute "AXDescription" of b) as text
                        if btnName contains "Call" or btnName contains "Video" or btnName contains "Face Time" then
                            perform action "AXPress" of b
                            return true
                        end if
                    end try
                    try
                        set btnTitle to (value of attribute "AXTitle" of b) as text
                        if btnTitle contains "Call" or btnTitle contains "Video" then
                            perform action "AXPress" of b
                            return true
                        end if
                    end try
                end repeat
                if n >= 1 then
                    perform action "AXPress" of (button 1 of w)
                    return true
                end if
            end try
        end if
        key code 36
    end tell
    """
    ok, err = run_applescript(axpress_script)
    if ok:
        logger.info("FaceTime: AXPress on Call/Video button")
        return True
    if err:
        logger.debug("FaceTime AXPress: %s", err[:200])
    time.sleep(0.5)

    # 5) Fallback: click by button name, or last button (Call is often rightmost)
    script = """
    tell application "System Events"
        if not (exists process "FaceTime") then return
        set ft to process "FaceTime"
        set frontmost of ft to true
        delay 0.5
        if exists window 1 of ft then
            set w to window 1 of ft
            set n to count of buttons of w
            if n >= 2 then
                try
                    click button n of w
                    return true
                end try
            end if
            try
                if exists (button "Call" of w) then
                    click button "Call" of w
                    return true
                end if
            end try
            try
                if exists (button "Video" of w) then
                    click button "Video" of w
                    return true
                end if
            end try
            try
                if exists (button "Audio" of w) then
                    click button "Audio" of w
                    return true
                end if
            end try
            try
                if exists (button "FaceTime" of w) then
                    click button "FaceTime" of w
                    return true
                end if
            end try
            try
                if n >= 1 then
                    click button 1 of w
                    return true
                end if
            end try
        end if
        key code 36
    end tell
    """
    ok, err = run_applescript(script)
    if ok:
        logger.info("FaceTime: clicked Call/Video or button 1")
        return True
    if err:
        logger.warning("FaceTime AppleScript: %s", err[:300])
    logger.info(
        "FaceTime: If the app opened but the call did not start, grant Accessibility to Terminal (or this app) in System Preferences > Privacy & Security > Accessibility."
    )
    return False


def _facetime_click_via_vision() -> bool:
    """Use Agent-S vision (Claude/grounding) to find and click the FaceTime Call/Video button. Returns True if successful."""
    try:
        r = requests.post(
            f"{AGENT_S_BASE_URL.rstrip('/')}/api/facetime_click_call",
            json={},
            timeout=30,
        )
        if r.ok:
            data = r.json()
            if data.get("success"):
                logger.info("FaceTime: vision click succeeded at (%s, %s)", data.get("x"), data.get("y"))
                return True
        logger.debug("FaceTime vision click failed or unavailable: %s", r.status_code if r else "no response")
    except requests.RequestException as e:
        logger.debug("FaceTime vision click request failed: %s", e)
    return False


def _run_facetime_call_and_share_screen(uri: str) -> None:
    """Run the Call button click (used from background thread). Try vision (Agent-S) first, then AppleScript; retry up to 3 times."""
    # 1) Try vision-based click (Claude/grounding in Agent-S) if Agent-S is running
    if _facetime_click_via_vision():
        return
    # 2) Fall back to AppleScript (accessibility) – retry up to 3 times
    for attempt in range(1, 4):
        try:
            if _facetime_click_call_button():
                return
        except Exception as e:
            logger.warning("FaceTime click attempt %s failed: %s", attempt, e)
        if attempt < 3:
            time.sleep(3)


def _start_facetime(phone_or_email: str) -> bool:
    """
    Start a FaceTime call on macOS: open facetime:// URL, then start a delayed background
    thread that clicks Call/Return once FaceTime has loaded (8s delay).
    """
    if not _is_darwin():
        logger.warning("FaceTime: only supported on macOS (current: %s)", platform.system())
        return False
    raw = (phone_or_email or "").strip().strip('"\'')
    normalized = _normalize_facetime_contact(raw)
    if not normalized:
        logger.warning("FaceTime: could not normalize contact %r", (phone_or_email or "")[:30])
        return False
    uri = f"facetime://{normalized}"
    logger.info("FaceTime: opening %s", normalized[:30] + "..." if len(normalized) > 30 else normalized)
    try:
        subprocess.run(
            ["open", uri],
            check=True,
            timeout=10,
            capture_output=True,
        )
        logger.info("FaceTime: opened successfully; will attempt to start call in 8s.")
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired) as e:
        logger.warning("FaceTime open failed: %s", e)
        return False
    # Run the "click Call" logic in a background thread after delay so FaceTime UI is ready
    delay_sec = max(5.0, min(60.0, FACETIME_CALL_DELAY_SEC))
    logger.info("FaceTime: will attempt to start call in %.0fs.", delay_sec)
    def delayed_click() -> None:
        time.sleep(delay_sec)
        _run_facetime_call_and_share_screen(uri)
    t = threading.Thread(target=delayed_click, name="facetime-click", daemon=True)
    t.start()
    return True


def _zoom_api_create_meeting() -> Optional[Tuple[str, str]]:
    """
    Create a Zoom instant meeting via Server-to-Server OAuth.
    Returns (join_url, meeting_id) or None on failure.
    """
    if not all([ZOOM_ACCOUNT_ID, ZOOM_CLIENT_ID, ZOOM_CLIENT_SECRET]):
        logger.info("Zoom API credentials not configured")
        return None

    # Get OAuth token
    token_url = "https://zoom.us/oauth/token"
    auth = base64.b64encode(
        f"{ZOOM_CLIENT_ID}:{ZOOM_CLIENT_SECRET}".encode()
    ).decode()
    headers = {
        "Authorization": f"Basic {auth}",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    data = {
        "grant_type": "account_credentials",
        "account_id": ZOOM_ACCOUNT_ID,
    }
    try:
        r = requests.post(token_url, headers=headers, data=data, timeout=10)
        r.raise_for_status()
        token = r.json().get("access_token")
        if not token:
            logger.warning("Zoom OAuth: no access_token in response")
            return None
    except requests.RequestException as e:
        logger.warning("Zoom OAuth failed: %s", e)
        return None

    # Create instant meeting (type=1)
    create_url = "https://api.zoom.us/v2/users/me/meetings"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    payload = {
        "topic": "Shadow-OS Video Call",
        "type": 1,  # Instant meeting
        "settings": {
            "join_before_host": True,
            "mute_upon_entry": False,
            "waiting_room": False,  # Anyone with link can join, no waiting room
            "approval_type": 0,  # Automatically approve all (no registration)
        },
    }
    try:
        r = requests.post(create_url, headers=headers, json=payload, timeout=10)
        r.raise_for_status()
        data = r.json()
        join_url = data.get("join_url", "")
        meeting_id = str(data.get("id", ""))
        if join_url:
            return (join_url, meeting_id)
    except requests.RequestException as e:
        logger.warning("Zoom create meeting failed: %s", e)
    return None


def _google_meet_via_browser() -> Optional[str]:
    """
    Create Google Meet by opening Chrome, navigating to meet.google.com/new,
    and extracting the URL from the address bar using pyautogui + pyperclip.
    Returns meeting URL or None.
    """
    try:
        import pyautogui
        import pyperclip
    except ImportError:
        logger.warning("pyautogui or pyperclip not available for Meet URL extraction")
        return None

    # Open default browser with meet.google.com/new
    try:
        if _is_windows():
            subprocess.Popen(
                ["cmd", "/c", "start", "https://meet.google.com/new"],
                shell=False,
            )
        else:
            import webbrowser
            webbrowser.open("https://meet.google.com/new")
    except Exception as e:
        logger.warning("Failed to open Chrome for Meet: %s", e)
        return None

    time.sleep(8)  # Wait for page load and redirect to meet.google.com/xxx-xxxx-xxx

    try:
        pyautogui.hotkey("ctrl", "l")  # Focus address bar
        time.sleep(0.3)
        pyautogui.hotkey("ctrl", "a")
        time.sleep(0.1)
        pyautogui.hotkey("ctrl", "c")
        time.sleep(0.2)
        url = pyperclip.paste()
        if url and "meet.google.com" in url:
            match = re.search(
                r"https?://meet\.google\.com/[a-z]{3}-[a-z]{4}-[a-z]{3}",
                url,
            )
            if match:
                return match.group(0)
            if url.startswith("http"):
                return url
    except Exception as e:
        logger.warning("Failed to extract Meet URL from clipboard: %s", e)
    return None


def _google_meet_via_stagehand() -> Optional[str]:
    """
    Create Google Meet via Stagehand: open meet.google.com/new and extract URL.
    Returns meeting URL or None.
    """
    instruction = (
        "Open Chrome and go to meet.google.com/new. "
        "Wait until the page fully loads and the URL in the address bar shows a meeting link like meet.google.com/xxx-xxxx-xxx. "
        "Copy the full URL from the address bar (Ctrl+L then Ctrl+C) and tell me the exact meeting link in your response."
    )
    try:
        r = requests.post(
            f"{STAGEHAND_SERVICE_URL.rstrip('/')}/api/execute",
            json={"instruction": instruction, "prompt": instruction},
            timeout=120,
        )
        if r.status_code != 200:
            return None
        result = r.json()
        msg = result.get("message", "") or ""
        match = re.search(
            r"https?://(?:meet\.google\.com/[a-z]{3}-[a-z]{4}-[a-z]{3}|meet\.google\.com/[a-zA-Z0-9_-]+)",
            msg,
        )
        if match:
            url = match.group(0)
            if not url.startswith("http"):
                url = "https://" + url
            return url
        match2 = re.search(r"meet\.google\.com/[a-z]{3}-[a-z]{4}-[a-z]{3}", msg)
        if match2:
            return "https://" + match2.group(0)
    except requests.RequestException as e:
        logger.warning("Google Meet via Stagehand failed: %s", e)
    return None


def _google_meet_create() -> Optional[str]:
    """Try Stagehand first, then browser+pyautogui fallback."""
    url = _google_meet_via_stagehand()
    if not url:
        url = _google_meet_via_browser()
    return url


def _whatsapp_video_call(phone_number: str) -> bool:
    """
    Initiate WhatsApp video call directly: open WhatsApp, search for contact,
    open chat, click video call button. No meeting link - direct call.
    """
    exe = _find_whatsapp_exe()
    if not exe or not phone_number:
        return False

    # Normalize: remove spaces, keep digits and +
    phone = re.sub(r"\s", "", str(phone_number))
    if not phone.startswith("+"):
        phone = "+" + phone
    # For search, use digits only (WhatsApp may match either format)
    search_digits = re.sub(r"\D", "", phone)

    try:
        import pyautogui
    except ImportError:
        logger.warning("pyautogui not available for WhatsApp automation")
        subprocess.Popen([str(exe)], shell=False)
        return True

    try:
        subprocess.Popen([str(exe)], shell=False)
        time.sleep(4)  # Wait for WhatsApp to load

        # Ctrl+F or Ctrl+Shift+F to open search
        pyautogui.hotkey("ctrl", "f")
        time.sleep(0.8)
        # Type phone number (or digits) to find contact
        pyautogui.write(search_digits, interval=0.05)
        time.sleep(1.5)
        pyautogui.press("enter")
        time.sleep(2)  # Chat opens

        # Video call button: typically top-right of chat header
        # WhatsApp Desktop: call icons are in header, video is usually right of voice
        w, h = pyautogui.size()
        # Click near top-right where video call icon usually is
        pyautogui.click(w - 80, 55)
        time.sleep(0.5)
        return True
    except Exception as e:
        logger.warning("WhatsApp video call automation failed: %s", e)
        # Fallback: at least we opened WhatsApp
        return True


def get_video_call_options(
    phone_number: Optional[str] = None,
    source: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Check availability of Zoom, Google Meet, WhatsApp, FaceTime (macOS).
    Returns dict with availability and recommended option.

    Smart choice: FaceTime (iMessage/Mac) or WhatsApp direct call (when we have number)
    - no link to send, call rings immediately. Zoom/Meet need links.
    """
    zoom_installed = _find_zoom_exe() is not None
    zoom_api_ok = bool(
        ZOOM_ACCOUNT_ID and ZOOM_CLIENT_ID and ZOOM_CLIENT_SECRET
    )
    zoom_ready = zoom_installed and zoom_api_ok

    whatsapp_installed = _find_whatsapp_exe() is not None
    meet_ready = True

    # FaceTime: macOS only; need contact from .env or iMessage (read env again so we're sure)
    has_facetime_contact = bool(
        (os.getenv("FACETIME_APPLE_ID") or "").strip()
        or (os.getenv("FACETIME_DEFAULT_NUMBER") or "").strip()
        or FACETIME_DEFAULT_NUMBER
        or FACETIME_APPLE_ID
    )
    if phone_number:
        pn = str(phone_number).replace("whatsapp:", "").strip()
        if pn and (pn.startswith("+") or "@" in pn or pn.replace(" ", "").replace("-", "").isdigit()):
            has_facetime_contact = True
    facetime_ready = _is_darwin() and has_facetime_contact

    # Extract phone for WhatsApp when user messaged from WhatsApp
    has_whatsapp_number = False
    if whatsapp_installed and phone_number:
        pn = str(phone_number).replace("whatsapp:", "").strip()
        if pn and (pn.startswith("+") or pn.replace(" ", "").isdigit()):
            has_whatsapp_number = True
    if whatsapp_installed and source and str(source).startswith("whatsapp:"):
        has_whatsapp_number = True

    options = []
    if facetime_ready:
        options.append(("facetime", "FaceTime (direct call – macOS)", 1))
    if zoom_ready:
        options.append(("zoom", "Zoom (meeting link)", 2))
    elif zoom_installed and not zoom_api_ok:
        options.append(("zoom", "Zoom (installed but no API)", 4))
    if meet_ready:
        options.append(("meet", "Google Meet (meeting link)", 3))
    if whatsapp_installed:
        if has_whatsapp_number:
            options.append(("whatsapp", "WhatsApp (direct call)", 1))
        else:
            options.append(("whatsapp", "WhatsApp (no number - open app)", 4))

    # Best option: FaceTime (Mac + number) > WhatsApp direct > Zoom > Meet
    recommended = None
    if facetime_ready:
        recommended = "facetime"
    elif whatsapp_installed and has_whatsapp_number:
        recommended = "whatsapp"
    elif zoom_ready:
        recommended = "zoom"
    elif meet_ready:
        recommended = "meet"
    elif whatsapp_installed:
        recommended = "whatsapp"

    return {
        "facetime_ready": facetime_ready,
        "zoom_installed": zoom_installed,
        "zoom_api_ready": zoom_api_ok,
        "zoom_ready": zoom_ready,
        "meet_ready": meet_ready,
        "whatsapp_installed": whatsapp_installed,
        "has_whatsapp_number": has_whatsapp_number,
        "options": options,
        "recommended": recommended,
    }


def start_video_call(
    target_platform: Optional[str] = None,
    phone_number: Optional[str] = None,
    source: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Start a video call. Chooses the most efficient option:
    - WhatsApp + user number → direct call (no link, rings immediately)
    - Zoom API → meeting link
    - Google Meet → meeting link

    Args:
        target_platform: Preferred platform (zoom, meet, whatsapp) or None for auto
        phone_number: User's phone number (for WhatsApp direct call)
        source: Message source (discord, slack, whatsapp) for reply routing

    Returns:
        {
            "success": bool,
            "message": str,
            "meeting_url": str | None,  # None for WhatsApp direct call
            "platform_used": str | None,
        }
    """
    # Extract phone for WhatsApp direct call
    phone_for_whatsapp = None
    if source and str(source).startswith("whatsapp:"):
        phone_for_whatsapp = str(source).replace("whatsapp:", "", 1).strip()
    elif phone_number:
        pn = str(phone_number).replace("whatsapp:", "").strip()
        if pn and (pn.startswith("+") or any(c.isdigit() for c in pn)):
            phone_for_whatsapp = pn if pn.startswith("+") else "+" + re.sub(r"\D", "", pn)

    options = get_video_call_options(
        phone_number=phone_for_whatsapp,
        source=source,
    )
    recommended = options.get("recommended")

    if not recommended:
        return {
            "success": False,
            "message": "No video call option available. Use iMessage with your number for FaceTime (Mac), or install Zoom (with API), WhatsApp Desktop, or Stagehand for Google Meet.",
            "meeting_url": None,
            "platform_used": None,
        }

    # Respect explicit preference if available
    choice = target_platform
    # When user explicitly asked for FaceTime ("FaceTime me"), always try it on macOS (don't require facetime_ready)
    if choice == "facetime":
        if _is_darwin():
            choice = "facetime"
        else:
            choice = None
    elif choice == "zoom" and options.get("zoom_ready"):
        pass
    elif choice == "meet" and options.get("meet_ready"):
        choice = "meet"
    elif choice == "whatsapp" and options.get("whatsapp_installed"):
        choice = "whatsapp"
    else:
        choice = recommended

    meeting_url = None
    platform_used = choice

    if choice == "facetime":
        # Prefer passed phone_number (e.g. sender from iMessage "FaceTime me") so we call the right person; fall back to .env
        raw_passed = (phone_number or "").strip() or (str(source).replace("whatsapp:", "").strip() if source else "")
        contact = raw_passed if raw_passed and _normalize_facetime_contact(raw_passed) else None
        contact = contact or (os.getenv("FACETIME_APPLE_ID") or "").strip() or (os.getenv("FACETIME_DEFAULT_NUMBER") or "").strip().strip('"\'') or FACETIME_APPLE_ID or FACETIME_DEFAULT_NUMBER
        if not contact:
            return {
                "success": False,
                "message": "FaceTime requires FACETIME_DEFAULT_NUMBER or FACETIME_APPLE_ID in .env, or message from iMessage with your number.",
                "meeting_url": None,
                "platform_used": None,
            }
        logger.info("FaceTime: using contact %s", contact[:30] + "..." if len(contact) > 30 else contact)
        ok = _start_facetime(contact)
        if ok:
            return {
                "success": True,
                "message": "Starting FaceTime with you – answer when it rings.",
                "meeting_url": None,
                "platform_used": "facetime",
            }
        return {
            "success": False,
            "message": "Could not start FaceTime. Ensure you're on macOS and FaceTime is available.",
            "meeting_url": None,
            "platform_used": None,
        }

    if choice == "zoom":
        result = _zoom_api_create_meeting()
        if result:
            meeting_url, _ = result
            # Launch Zoom or open join URL so PC joins
            zoom_exe = _find_zoom_exe()
            try:
                if zoom_exe and _is_windows():
                    subprocess.Popen(
                        ["cmd", "/c", "start", meeting_url],
                        shell=False,
                    )
                elif zoom_exe:
                    subprocess.Popen([str(zoom_exe), meeting_url], shell=False)
                else:
                    # Open in default browser
                    if _is_windows():
                        subprocess.Popen(
                            ["cmd", "/c", "start", meeting_url],
                            shell=False,
                        )
                    else:
                        import webbrowser
                        webbrowser.open(meeting_url)
            except Exception as e:
                logger.warning("Failed to launch Zoom/browser: %s", e)
            return {
                "success": True,
                "message": f"Join the Zoom call: {meeting_url}",
                "meeting_url": meeting_url,
                "platform_used": "zoom",
            }
        return {
            "success": False,
            "message": "Zoom API failed. Falling back to Google Meet.",
            "meeting_url": None,
            "platform_used": None,
        }

    if choice == "meet":
        meeting_url = _google_meet_create()
        if meeting_url:
            return {
                "success": True,
                "message": f"Join the Google Meet: {meeting_url}",
                "meeting_url": meeting_url,
                "platform_used": "meet",
            }
        return {
            "success": False,
            "message": "Could not create Google Meet. Ensure Stagehand is running and Chrome can open meet.google.com.",
            "meeting_url": None,
            "platform_used": None,
        }

    if choice == "whatsapp":
        ok = _whatsapp_video_call(phone_for_whatsapp or "")
        if ok:
            return {
                "success": True,
                "message": "Calling you now on WhatsApp – answer when it rings.",
                "meeting_url": None,
                "platform_used": "whatsapp",
            }
        return {
            "success": False,
            "message": "Could not start WhatsApp call. Ensure WhatsApp Desktop is installed and you messaged from WhatsApp.",
            "meeting_url": None,
            "platform_used": None,
        }

    return {
        "success": False,
        "message": "No video call option could be used.",
        "meeting_url": None,
        "platform_used": None,
    }


def is_video_call_request(text: str) -> bool:
    """Detect if the user is asking for a video call (including FaceTime)."""
    if not text or not isinstance(text, str):
        return False
    t = text.strip().lower()
    # Match "facetime" as single word or with "me" so "FaceTime me" / "facetime me" always hits
    if "facetime" in t or "face time" in t:
        return True
    patterns = [
        "video call",
        "video call me",
        "call me",
        "video chat",
        "start a video call",
        "start video call",
        "zoom me",
        "google meet",
        "meet call",
        "whatsapp video",
        "whatsapp call",
    ]
    return any(p in t for p in patterns)
