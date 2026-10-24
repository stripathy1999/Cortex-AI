#!/usr/bin/env python3
"""
Windows message bridge: receive commands from Discord, Slack, and WhatsApp.
Only processes messages from the configured allowed user (you).

Supported: Discord, Slack, WhatsApp (Twilio)
"""

from __future__ import annotations

import argparse
import logging
import os
import re
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
from dotenv import load_dotenv
from flask import Flask, jsonify, request, Response

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=ENV_PATH)

logger = logging.getLogger(__name__)
app = Flask(__name__)

# Platform tokens
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN", "")
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN", "")
SLACK_APP_TOKEN = os.getenv("SLACK_APP_TOKEN", "")
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_WHATSAPP_NUMBER = os.getenv("TWILIO_WHATSAPP_NUMBER", "")  # e.g. whatsapp:+14155238886

# Allowed user - ONLY messages from this user are processed
ALLOWED_DISCORD_USER_ID = os.getenv("ALLOWED_DISCORD_USER_ID", "").strip()
ALLOWED_SLACK_USER_ID = os.getenv("ALLOWED_SLACK_USER_ID", "").strip()
ALLOWED_WHATSAPP_PHONE = os.getenv("ALLOWED_WHATSAPP_PHONE", "").strip()  # e.g. +1234567890

# Comma-separated: discord, slack, whatsapp
MESSAGE_SOURCES = [s.strip().lower() for s in os.getenv("MESSAGE_SOURCES", "discord").split(",") if s.strip()]

BACKEND_BASE_URL = os.getenv(
    "BACKEND_BASE_URL",
    f"http://{os.getenv('SERVER_HOST', '127.0.0.1')}:{os.getenv('SERVER_PORT', '8003')}",
)
POLL_INTERVAL = float(os.getenv("WINDOWS_BRIDGE_POLL_INTERVAL", "2.0"))
# Default 8101 so Windows bridge can run alongside iMessage bridge (8100). Override with WINDOWS_BRIDGE_PORT.
WINDOWS_BRIDGE_PORT = int(os.getenv("WINDOWS_BRIDGE_PORT", os.getenv("IMESSAGE_BRIDGE_PORT", "8101")))
WINDOWS_BRIDGE_HOST = os.getenv("IMESSAGE_BRIDGE_HOST", os.getenv("WINDOWS_BRIDGE_HOST", "127.0.0.1"))


def _deliver_to_backend(payload: Dict[str, Any]) -> None:
    try:
        r = requests.post(
            f"{BACKEND_BASE_URL.rstrip('/')}/api/new_imessage",
            json=payload,
            timeout=30,
        )
        r.raise_for_status()
        logger.info("Delivered message to backend from %s", payload.get("source", "?"))
    except requests.RequestException as e:
        logger.exception("Failed to deliver to backend: %s", e)


def _is_allowed_discord(user_id: int) -> bool:
    if not ALLOWED_DISCORD_USER_ID:
        logger.warning("ALLOWED_DISCORD_USER_ID not set - rejecting all Discord messages")
        return False
    return str(user_id) == ALLOWED_DISCORD_USER_ID


def _is_allowed_slack(user_id: str) -> bool:
    if not ALLOWED_SLACK_USER_ID:
        logger.warning("ALLOWED_SLACK_USER_ID not set - rejecting all Slack messages")
        return False
    return user_id == ALLOWED_SLACK_USER_ID


def _is_allowed_whatsapp(from_number: str) -> bool:
    if not ALLOWED_WHATSAPP_PHONE:
        logger.warning("ALLOWED_WHATSAPP_PHONE not set - rejecting all WhatsApp messages")
        return False
    # Normalize: remove spaces, ensure + prefix
    from_norm = re.sub(r"\s", "", from_number)
    if not from_norm.startswith("+"):
        from_norm = "+" + from_norm
    allowed_norm = re.sub(r"\s", "", ALLOWED_WHATSAPP_PHONE)
    if not allowed_norm.startswith("+"):
        allowed_norm = "+" + allowed_norm
    return from_norm == allowed_norm


# --- Discord ---
def _discord_run_bot() -> None:
    if not DISCORD_BOT_TOKEN:
        return
    try:
        import discord
        from discord.ext import commands
    except ImportError:
        logger.error("discord.py not installed. Run: uv add '.[discord]'")
        return

    intents = discord.Intents.default()
    intents.message_content = True
    intents.dm_messages = True
    bot = commands.Bot(command_prefix="!", intents=intents)

    @bot.event
    async def on_ready():
        logger.info("Discord bot ready: %s", bot.user)

    @bot.event
    async def on_message(message: discord.Message):
        if message.author.bot:
            return
        if not _is_allowed_discord(message.author.id):
            logger.debug("Ignoring Discord message from non-allowed user %s", message.author.id)
            return
        text = (message.content or "").strip()
        if not text:
            return

        channel_id = message.channel.id
        author = message.author
        name = author.display_name or author.name or "Unknown"
        target = f"discord:{channel_id}"

        payload = {
            "rowid": message.id,
            "text": text,
            "received_at": datetime.now(timezone.utc).isoformat(),
            "display_name": name,
            "phone_number": target,
            "conversation": f"Discord {name}",
            "is_group": isinstance(message.channel, discord.TextChannel),
            "contact_label": name,
            "source": target,
        }
        _deliver_to_backend(payload)

    try:
        bot.run(DISCORD_BOT_TOKEN, log_handler=None)
    except Exception as e:
        logger.exception("Discord bot error: %s", e)


def _discord_send(channel_id: str, text: str, attachments: Optional[list[str]] = None) -> bool:
    if not DISCORD_BOT_TOKEN:
        return False
    url = f"https://discord.com/api/v10/channels/{channel_id}/messages"
    headers = {"Authorization": f"Bot {DISCORD_BOT_TOKEN}", "Content-Type": "application/json"}
    try:
        resp = requests.post(url, headers=headers, json={"content": text}, timeout=10)
        resp.raise_for_status()
        return True
    except Exception as e:
        logger.error("Discord send failed: %s", e)
        return False


# --- Slack ---
def _slack_run_bot() -> None:
    if not SLACK_BOT_TOKEN or not SLACK_APP_TOKEN:
        return
    try:
        from slack_bolt import App
        from slack_bolt.adapter.socket_mode import SocketModeHandler
    except ImportError:
        logger.error("slack-bolt not installed. Run: uv add '.[slack]'")
        return

    slack_app = App(token=SLACK_BOT_TOKEN)

    @slack_app.event("message")
    def handle_message(event, say):
        if event.get("subtype") in ("bot_message", "message_changed", "message_deleted"):
            return
        user_id = event.get("user", "")
        if not _is_allowed_slack(user_id):
            logger.debug("Ignoring Slack message from non-allowed user %s", user_id)
            return
        text = (event.get("text") or "").strip()
        if not text:
            return
        channel_id = event.get("channel", "")
        target = f"slack:{channel_id}"

        payload = {
            "rowid": event.get("ts", ""),
            "text": text,
            "received_at": datetime.now(timezone.utc).isoformat(),
            "display_name": user_id,
            "phone_number": target,
            "conversation": f"Slack {user_id}",
            "is_group": channel_id.startswith("C") or channel_id.startswith("G"),
            "contact_label": user_id,
            "source": target,
        }
        _deliver_to_backend(payload)

    try:
        handler = SocketModeHandler(slack_app, SLACK_APP_TOKEN)
        handler.start()
    except Exception as e:
        logger.exception("Slack bot error: %s", e)


def _slack_send(channel_id: str, text: str, attachments: Optional[list[str]] = None) -> bool:
    if not SLACK_BOT_TOKEN:
        return False
    url = "https://slack.com/api/chat.postMessage"
    headers = {"Authorization": f"Bearer {SLACK_BOT_TOKEN}", "Content-Type": "application/json"}
    try:
        resp = requests.post(
            url,
            headers=headers,
            json={"channel": channel_id, "text": text},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        if not data.get("ok"):
            logger.error("Slack API error: %s", data)
            return False
        return True
    except Exception as e:
        logger.error("Slack send failed: %s", e)
        return False


# --- WhatsApp (Twilio) ---
def _whatsapp_send(to_number: str, text: str, attachments: Optional[list[str]] = None) -> bool:
    if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN or not TWILIO_WHATSAPP_NUMBER:
        return False
    to_whatsapp = to_number if to_number.startswith("whatsapp:") else f"whatsapp:{to_number}"
    url = f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_ACCOUNT_SID}/Messages.json"
    auth = (TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    try:
        data = {"From": TWILIO_WHATSAPP_NUMBER, "To": to_whatsapp, "Body": text}
        resp = requests.post(url, auth=auth, data=data, timeout=15)
        resp.raise_for_status()
        return True
    except Exception as e:
        logger.error("WhatsApp send failed: %s", e)
        return False


# --- Flask routes ---
@app.route("/health", methods=["GET"])
def health() -> Any:
    return jsonify({"status": "ok", "sources": MESSAGE_SOURCES}), 200


@app.route("/webhooks/whatsapp", methods=["POST"])
def webhook_whatsapp() -> Response:
    """Twilio webhook for incoming WhatsApp messages."""
    if "whatsapp" not in MESSAGE_SOURCES:
        return Response(status=200)
    from_number = request.form.get("From", "").replace("whatsapp:", "")
    body = (request.form.get("Body") or "").strip()
    if not body:
        return _twiml_response("")
    if not _is_allowed_whatsapp(from_number):
        logger.debug("Ignoring WhatsApp message from non-allowed number %s", from_number)
        return _twiml_response("")
    target = f"whatsapp:{from_number}"
    payload = {
        "rowid": request.form.get("MessageSid", ""),
        "text": body,
        "received_at": datetime.now(timezone.utc).isoformat(),
        "display_name": from_number,
        "phone_number": target,
        "conversation": f"WhatsApp {from_number}",
        "is_group": False,
        "contact_label": from_number,
        "source": target,
    }
    _deliver_to_backend(payload)
    return _twiml_response("")


def _twiml_response(text: str) -> Response:
    try:
        from twilio.twiml.messaging_response import MessagingResponse
    except ImportError:
        return Response(status=200)
    resp = MessagingResponse()
    if text:
        resp.message(text)
    return Response(str(resp), mimetype="application/xml")


@app.route("/api/send_imessage", methods=["POST"])
def api_send_message() -> Any:
    """Send a message back. Target format: platform:id (e.g. discord:123, slack:C123, whatsapp:+123)"""
    payload = request.get_json(silent=True) or {}
    target = (payload.get("target") or "").strip()
    text = payload.get("text")
    attachments = payload.get("attachments")

    if not target:
        return jsonify({"error": "target is required"}), 400
    if text is None or not str(text).strip():
        return jsonify({"error": "text is required"}), 400

    text = str(text).strip()
    ok = False

    if target.startswith("discord:"):
        channel_id = target.replace("discord:", "", 1)
        ok = _discord_send(channel_id, text, attachments)
    elif target.startswith("slack:"):
        channel_id = target.replace("slack:", "", 1)
        ok = _slack_send(channel_id, text, attachments)
    elif target.startswith("whatsapp:"):
        to_number = target.replace("whatsapp:", "", 1)
        ok = _whatsapp_send(to_number, text, attachments)
    else:
        # Legacy: assume Discord channel ID if numeric
        if target.isdigit():
            ok = _discord_send(target, text, attachments)
        else:
            return jsonify({"error": "target must be platform:id (discord:, slack:, whatsapp:)"}), 400

    if ok:
        return jsonify({"status": "sent"}), 200
    return jsonify({"status": "failed", "error": "Send failed"}), 500


def main() -> int:
    parser = argparse.ArgumentParser(description="Windows message bridge (Discord, Slack, WhatsApp)")
    parser.add_argument("--port", type=int, default=WINDOWS_BRIDGE_PORT)
    parser.add_argument("--host", default=WINDOWS_BRIDGE_HOST)
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    threads: List[threading.Thread] = []

    if "discord" in MESSAGE_SOURCES and DISCORD_BOT_TOKEN:
        if not ALLOWED_DISCORD_USER_ID:
            logger.warning("DISCORD_BOT_TOKEN set but ALLOWED_DISCORD_USER_ID empty - no messages will be processed")
        t = threading.Thread(target=_discord_run_bot, daemon=True)
        t.start()
        threads.append(t)
        logger.info("Discord bridge started (allowed user: %s)", ALLOWED_DISCORD_USER_ID or "NOT SET")
    elif "discord" in MESSAGE_SOURCES:
        logger.warning("Discord in MESSAGE_SOURCES but DISCORD_BOT_TOKEN not set")

    if "slack" in MESSAGE_SOURCES and SLACK_BOT_TOKEN and SLACK_APP_TOKEN:
        if not ALLOWED_SLACK_USER_ID:
            logger.warning("Slack tokens set but ALLOWED_SLACK_USER_ID empty - no messages will be processed")
        t = threading.Thread(target=_slack_run_bot, daemon=True)
        t.start()
        threads.append(t)
        logger.info("Slack bridge started (allowed user: %s)", ALLOWED_SLACK_USER_ID or "NOT SET")
    elif "slack" in MESSAGE_SOURCES:
        logger.warning("Slack in MESSAGE_SOURCES but SLACK_BOT_TOKEN or SLACK_APP_TOKEN not set")

    if "whatsapp" in MESSAGE_SOURCES:
        if TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN and TWILIO_WHATSAPP_NUMBER:
            if not ALLOWED_WHATSAPP_PHONE:
                logger.warning("Twilio set but ALLOWED_WHATSAPP_PHONE empty - no messages will be processed")
            logger.info("WhatsApp (Twilio) webhook at /webhooks/whatsapp (allowed: %s)", ALLOWED_WHATSAPP_PHONE or "NOT SET")
        else:
            logger.warning("WhatsApp in MESSAGE_SOURCES but Twilio credentials not set")

    if not threads and "whatsapp" not in MESSAGE_SOURCES:
        logger.error("No message sources configured. Set MESSAGE_SOURCES and required tokens.")
        return 1

    logger.info("Windows message bridge on %s:%s (sources: %s)", args.host, args.port, MESSAGE_SOURCES)
    app.run(host=args.host, port=args.port, debug=False, use_reloader=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
