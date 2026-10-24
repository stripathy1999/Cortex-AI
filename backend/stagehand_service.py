#!/usr/bin/env python3
"""
Stagehand browser automation service.
Handles browser tasks: "Open Chrome and search X on Google", "Go to YouTube Music and play music", etc.
Uses Browserbase Stagehand for accurate, AI-powered browser control.
"""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path

import requests
from dotenv import load_dotenv
from flask import Flask, jsonify, request

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=ENV_PATH)

logger = logging.getLogger(__name__)
app = Flask(__name__)

STAGEHAND_PORT = int(os.getenv("STAGEHAND_SERVICE_PORT", "5005"))
STAGEHAND_HOST = os.getenv("STAGEHAND_SERVICE_HOST", "127.0.0.1")
USE_BROWSERBASE = os.getenv("STAGEHAND_USE_BROWSERBASE", "false").lower() in ("1", "true", "yes")
BROWSERBASE_API_KEY = os.getenv("BROWSERBASE_API_KEY", "")
BROWSERBASE_PROJECT_ID = os.getenv("BROWSERBASE_PROJECT_ID", "")
# Context ID for persistent logins/cookies (env or data/browserbase_context.txt)
BROWSERBASE_CONTEXT_ID = os.getenv("BROWSERBASE_CONTEXT_ID", "").strip()
CHROME_USER_DATA_DIR = os.getenv("CHROME_USER_DATA_DIR", "").strip()
CHROME_PATH = os.getenv("CHROME_PATH", "").strip() or "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
# Stagehand model config: use correct key per provider
MODEL_NAME = os.getenv("STAGEHAND_MODEL", "openai/gpt-4o-mini")
# Planner model: use a fast model for "think" step. Haiku/Gemini Flash = faster, Sonnet = slightly better quality
PLANNER_MODEL = (os.getenv("STAGEHAND_PLANNER_MODEL") or "").strip() or "claude-3-5-haiku-20241022"


def _get_model_api_key() -> str:
    """Return the API key for the configured model (Anthropic, Google, OpenAI)."""
    mn = (MODEL_NAME or "").lower()
    if mn.startswith("anthropic/"):
        return (os.getenv("ANTHROPIC_API_KEY") or "").strip()
    if mn.startswith("google/"):
        return (os.getenv("GOOGLE_GENERATIVE_AI_API_KEY") or os.getenv("GEMINI_API_KEY") or "").strip()
    return (os.getenv("MODEL_API_KEY") or os.getenv("OPENAI_API_KEY") or "").strip()


MODEL_API_KEY = _get_model_api_key()
MAX_STEPS = int(os.getenv("STAGEHAND_MAX_STEPS", "30"))
EXECUTE_TIMEOUT = float(os.getenv("STAGEHAND_EXECUTE_TIMEOUT", "300"))
# Seconds to keep browser open after task completes (0 = close immediately). API response is delayed.
KEEP_OPEN_SECONDS = int(os.getenv("STAGEHAND_KEEP_OPEN_SECONDS", "120"))


DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CONTEXT_FILE = DATA_DIR / "browserbase_context.txt"


def _get_browserbase_context_id() -> str:
    """Get Browserbase context ID from env or data/browserbase_context.txt."""
    if BROWSERBASE_CONTEXT_ID:
        return BROWSERBASE_CONTEXT_ID
    if CONTEXT_FILE.exists():
        try:
            return CONTEXT_FILE.read_text().strip()
        except OSError:
            pass
    return ""


def _is_browser_task(text: str) -> bool:
    """Check if the message describes a browser-related task.
    Excludes desktop-only tasks like 'Open Notepad'."""
    if not text or not isinstance(text, str):
        return False
    t = text.lower()
    if any(desktop in t for desktop in ("notepad", "calculator", "calc", "cmd", "explorer", "file explorer")):
        return False
    keywords = [
        "chrome", "browser", "google", "search", "youtube", "music.youtube",
        "youtube music", "go to", "navigate", "website", "web", "browse",
        "spotify", "netflix", "gmail", "facebook", "twitter", "instagram",
    ]
    return any(k in t for k in keywords)


def _plan_browser_task(raw_prompt: str) -> str:
    """
    Think first: convert user prompt into a clear, step-by-step browser instruction.
    Uses fastest available planner: Gemini Flash (if key set) > Claude Haiku > OpenAI.
    """
    openai_key = (os.getenv("OPENAI_API_KEY") or os.getenv("MODEL_API_KEY") or "").strip()
    anthropic_key = (os.getenv("ANTHROPIC_API_KEY") or "").strip()
    gemini_key = (os.getenv("GOOGLE_GENERATIVE_AI_API_KEY") or os.getenv("GEMINI_API_KEY") or "").strip()

    system = """You are an elite browser automation planner. Convert the user's request into ONE precise, complete instruction for a world-class browser agent.

PRINCIPLES: Be exhaustive. Include every step. No shortcuts. The agent must know exactly what to do.

RULES:
1. SEARCH + OPEN FIRST: "Go to google.com, type [query] in the search box, press Enter, wait for results to load. Dismiss any cookie/consent banner if shown. Click the FIRST organic search result (the first blue link in the main results area—skip 'Ad', 'Sponsored', and 'People also ask' sections). Wait for that page to load. You are done when the first result's page is fully visible."
2. SITE-SPECIFIC: Go directly to the site URL first (e.g. linkedin.com, youtube.com, gmail.com), then perform every action the user asked. If they want to "search X on LinkedIn", go to linkedin.com and use LinkedIn's search.
3. MULTI-STEP: Break complex requests into an ordered sequence. Example: "Go to X, do A, then do B, then do C. Confirm the final state."
4. HANDLE EDGE CASES: Include "if you see a cookie/consent banner, click Accept or OK" when relevant. Include "if login appears, click Sign in with Google" when the site commonly requires it.
5. Output ONLY the instruction. Be specific: exact URLs, what to type, what to click, in order."""

    user_msg = f"User request: {raw_prompt}\n\nInstruction for browser agent:"

    # 1. Gemini (fastest) – if key set and planner model is Gemini
    if gemini_key and PLANNER_MODEL.startswith("gemini"):
        try:
            model_id = PLANNER_MODEL if "/" not in PLANNER_MODEL else PLANNER_MODEL.split("/")[-1]
            r = requests.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{model_id}:generateContent",
                headers={"x-goog-api-key": gemini_key, "Content-Type": "application/json"},
                json={
                    "systemInstruction": {"parts": [{"text": system}]},
                    "contents": [{"parts": [{"text": user_msg}]}],
                    "generationConfig": {"maxOutputTokens": 800, "temperature": 0.2},
                },
                timeout=12,
            )
            r.raise_for_status()
            data = r.json()
            cand = data.get("candidates", [{}])[0]
            parts = cand.get("content", {}).get("parts", [])
            text = (parts[0].get("text", "") if parts else "").strip()
            if text:
                logger.info("Planner (Gemini) output: %s", text[:120] + "..." if len(text) > 120 else text)
                return text
        except Exception as e:
            logger.warning("Planner (Gemini) failed: %s", e)

    # 2. Anthropic (Haiku default = fast; use Sonnet for max quality)
    if anthropic_key:
        try:
            model_id = PLANNER_MODEL.split("/")[-1] if "/" in PLANNER_MODEL else PLANNER_MODEL
            if not model_id.startswith("claude-"):
                model_id = "claude-3-5-haiku-20241022"
            r = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": anthropic_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model_id,
                    "max_tokens": 800,
                    "system": system,
                    "messages": [{"role": "user", "content": user_msg}],
                },
                timeout=15,
            )
            r.raise_for_status()
            data = r.json()
            text = data.get("content", [{}])[0].get("text", "").strip()
            if text:
                logger.info("Planner (Anthropic) output: %s", text[:120] + "..." if len(text) > 120 else text)
                return text
        except Exception as e:
            logger.warning("Planner (Anthropic) failed: %s, using raw prompt", e)

    if openai_key:
        try:
            r = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {openai_key}", "Content-Type": "application/json"},
                json={
                    "model": "gpt-4o-mini",
                    "max_tokens": 800,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user_msg},
                    ],
                },
                timeout=15,
            )
            r.raise_for_status()
            data = r.json()
            text = (data.get("choices", [{}])[0].get("message", {}).get("content") or "").strip()
            if text:
                logger.info("Planner output: %s", text[:120] + "..." if len(text) > 120 else text)
                return text
        except Exception as e:
            logger.warning("Planner (OpenAI) failed: %s, using raw prompt", e)

    return raw_prompt


def _run_stagehand_async(instruction: str) -> dict:
    """Run Stagehand execute in a new event loop (Flask is sync)."""
    try:
        from stagehand import AsyncStagehand
    except ImportError:
        logger.error("stagehand not installed. Run: uv add stagehand")
        return {"success": False, "message": "Stagehand not installed", "error": "ImportError"}

    async def _execute():
        if USE_BROWSERBASE and BROWSERBASE_API_KEY and BROWSERBASE_PROJECT_ID:
            if not MODEL_API_KEY:
                hint = "ANTHROPIC_API_KEY" if (MODEL_NAME or "").lower().startswith("anthropic/") else "GOOGLE_GENERATIVE_AI_API_KEY or GEMINI_API_KEY" if (MODEL_NAME or "").lower().startswith("google/") else "MODEL_API_KEY or OPENAI_API_KEY"
                return {
                    "success": False,
                    "message": f"Set {hint} in .env for Stagehand",
                    "error": "MissingModelKey",
                }
            client = AsyncStagehand(
                browserbase_api_key=BROWSERBASE_API_KEY,
                browserbase_project_id=BROWSERBASE_PROJECT_ID,
                model_api_key=MODEL_API_KEY,
            )
        else:
            # Local mode - runs Chrome on this machine
            # Stagehand SDK requires model_api_key (from MODEL_API_KEY env) in all modes
            if not MODEL_API_KEY:
                hint = "ANTHROPIC_API_KEY" if (MODEL_NAME or "").lower().startswith("anthropic/") else "GOOGLE_GENERATIVE_AI_API_KEY or GEMINI_API_KEY" if (MODEL_NAME or "").lower().startswith("google/") else "MODEL_API_KEY or OPENAI_API_KEY"
                return {
                    "success": False,
                    "message": f"Set {hint} in .env for Stagehand",
                    "error": "MissingModelKey",
                }
            client = AsyncStagehand(
                server="local",
                model_api_key=MODEL_API_KEY,
                local_openai_api_key=MODEL_API_KEY,
                local_ready_timeout_s=30.0,
                local_headless=False,  # Show Chrome window on user's PC
                local_chrome_path=CHROME_PATH if os.path.isfile(CHROME_PATH) else None,
            )

        session = None
        try:
            # Build session start options
            start_kwargs = {"model_name": MODEL_NAME}

            if USE_BROWSERBASE:
                # Pass persistent context (Chrome cookies) + keepAlive so user can open Live View to log in if needed
                context_id = _get_browserbase_context_id()
                bb_params: dict = {"keep_alive": True}
                if context_id:
                    bb_params["browser_settings"] = {
                        "context": {"id": context_id, "persist": True}
                    }
                    logger.info("Using Browserbase context %s for persistent logins", context_id[:12] + "...")
                else:
                    logger.warning(
                        "Browserbase mode: no context configured. Run: python scripts/create_browserbase_context.py && python sync_chrome_to_browserbase.py"
                    )
                start_kwargs["browserbase_session_create_params"] = bb_params
            else:
                # Local mode: Chrome opens on user's laptop. API requires launchOptions.
                # Use minimal options - user_data_dir causes Chrome crash (Stagehand bug #1128).
                start_kwargs["browser"] = {
                    "type": "local",
                    "launch_options": {"headless": False},
                }
            session = await client.sessions.start(**start_kwargs)
            session_id = getattr(session, "id", None) or (session.data.session_id if hasattr(session, "data") else None)
            logger.info("Stagehand session started: %s", session_id)

            # Use instruction as-is; Stagehand's agent understands natural language
            inst = instruction.strip()

            # System prompt: king of browser automation - elite, autonomous, thorough
            system_prompt = (
                "You are the world's best browser automation agent. You complete tasks fully, correctly, and autonomously. Never stop early.\n\n"
                "CORE PRINCIPLES:\n"
                "1. EXHAUSTIVE: Do every step. If the user says 'search X and open first link', you MUST: (a) go to Google, (b) search, (c) click the FIRST organic result (first blue link in main results—skip 'Ad'/'Sponsored'/'People also ask'), (d) wait for that page to load. Done only when the first result's page is visible.\n"
                "2. ROBUST: If a cookie/consent banner appears, click Accept/OK/Agree. If a login page appears, click 'Sign in with Google' or 'Continue with Google'. If an element isn't found, try scrolling or waiting; try alternate selectors.\n"
                "3. PRECISE: For 'first result'—identify the first organic result in the main search results area. Skip sponsored blocks. Click the actual link, not a parent div.\n"
                "4. SITE-SPECIFIC: For LinkedIn/YouTube/Gmail/etc., go directly to that site first, then use that site's features (e.g. LinkedIn search, not Google).\n"
                "5. VERIFY: After each major step, confirm the page loaded or the action succeeded before proceeding.\n"
                "6. STAY: When complete, leave the browser on the final page. Do not close or navigate away."
            )

            # session.execute is the agent execution (full example pattern)
            execute_resp = await session.execute(
                execute_options={
                    "instruction": inst,
                    "max_steps": MAX_STEPS,
                },
                agent_config={
                    "model": {
                        "model_name": MODEL_NAME,
                        "api_key": MODEL_API_KEY,
                    },
                    "system_prompt": system_prompt,
                    "cua": False,
                },
                timeout=EXECUTE_TIMEOUT,
            )
            result = execute_resp.data.result if hasattr(execute_resp, "data") else getattr(execute_resp, "result", execute_resp)
            success = getattr(result, "success", result.get("success", False) if isinstance(result, dict) else False)
            message = getattr(result, "message", result.get("message", "Done") if isinstance(result, dict) else "Done")

            # Build response with Live View URL (user can watch / log in manually if auth fails)
            live_view = f"https://browserbase.com/sessions/{session_id}" if session_id else None

            # Keep browser open for user to see/interact (local mode). API response is delayed.
            if not USE_BROWSERBASE and KEEP_OPEN_SECONDS > 0:
                logger.info("Keeping browser open for %s seconds...", KEEP_OPEN_SECONDS)
                await asyncio.sleep(KEEP_OPEN_SECONDS)

            resp = {"success": success, "message": message}
            if live_view:
                resp["live_view"] = live_view
            return resp
        finally:
            if session:
                try:
                    await session.end()
                except Exception as e:
                    logger.warning("Stagehand session end error: %s", e)
            if hasattr(client, "close"):
                await client.close()

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(_execute())
    except Exception as e:
        logger.exception("Stagehand execute error: %s", e)
        return {"success": False, "message": str(e), "error": type(e).__name__}


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "stagehand": "ready"}), 200


@app.route("/api/status", methods=["GET"])
def status():
    """Return cloud context status for debugging."""
    mode = "browserbase" if USE_BROWSERBASE else "local"
    ctx_id = _get_browserbase_context_id()
    payload = {
        "status": "ok",
        "mode": mode,
        "context_configured": bool(ctx_id),
    }
    if ctx_id:
        payload["context_id"] = ctx_id[:12] + "..."
    return jsonify(payload), 200


@app.route("/api/execute", methods=["POST"])
def execute():
    """Execute a browser task via Stagehand. Architecture: Think (plan) → Execute."""
    payload = request.get_json(silent=True) or {}
    raw = (payload.get("instruction") or payload.get("prompt") or "").strip()
    if not raw:
        return jsonify({"error": "instruction is required"}), 400

    # Step 1: Think – plan the task (avoid Google search for site-specific tasks)
    instruction = _plan_browser_task(raw)
    logger.info("Stagehand execute (planned): %s", instruction[:120])

    # Step 2: Execute – run Browserbase/Stagehand with the planned instruction
    result = _run_stagehand_async(instruction)
    return jsonify(result), 200


@app.route("/api/is_browser_task", methods=["POST"])
def is_browser_task():
    """Check if a message describes a browser task (for routing)."""
    payload = request.get_json(silent=True) or {}
    text = payload.get("text", "")
    return jsonify({"is_browser_task": _is_browser_task(text)}), 200


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    mode = "Browserbase" if USE_BROWSERBASE else "local"
    logger.info("Stagehand service (%s) on %s:%s", mode, STAGEHAND_HOST, STAGEHAND_PORT)
    app.run(host=STAGEHAND_HOST, port=STAGEHAND_PORT, debug=False, use_reloader=False, threaded=True)


if __name__ == "__main__":
    main()
