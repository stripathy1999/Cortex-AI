#!/usr/bin/env python3
"""
Low-latency cursor control for Vision-Driven Mirror Agent.

Listens for cursor_move and cursor_click events via Socket.IO.
Moves/clicks the mouse using PyAutoGUI for <100ms feedback.

Start only when ENABLE_VISION_MIRROR=true. Does not affect existing services.
"""
from __future__ import annotations

import logging
import os

try:
    import pyautogui
    PYAUTOGUI_AVAILABLE = True
except ImportError:
    PYAUTOGUI_AVAILABLE = False
    pyautogui = None

from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_socketio import SocketIO, emit

CURSOR_PORT = int(os.getenv("CURSOR_SERVICE_PORT", "5004"))

app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Reduce PyAutoGUI failsafe delay for responsiveness
if PYAUTOGUI_AVAILABLE:
    pyautogui.FAILSAFE = True
    pyautogui.PAUSE = 0.02


@socketio.on("connect")
def on_connect():
    logger.info("Cursor client connected")


@socketio.on("disconnect")
def on_disconnect():
    logger.info("Cursor client disconnected")


@socketio.on("cursor_move")
def on_cursor_move(data):
    """Move cursor to (x, y). Expects { x: int, y: int }."""
    if not PYAUTOGUI_AVAILABLE:
        emit("error", {"message": "pyautogui not installed"})
        return
    try:
        x = int(data.get("x", 0))
        y = int(data.get("y", 0))
        pyautogui.moveTo(x, y, duration=0.05)
        emit("cursor_moved", {"x": x, "y": y})
    except Exception as e:
        logger.warning("cursor_move error: %s", e)
        emit("error", {"message": str(e)})


@app.route("/api/cursor_move", methods=["POST"])
def api_cursor_move():
    """HTTP endpoint for cursor move (e.g. from main.py proxy)."""
    if not PYAUTOGUI_AVAILABLE:
        return jsonify({"error": "pyautogui not installed"}), 503
    payload = request.get_json(silent=True) or {}
    try:
        x = int(payload.get("x", 0))
        y = int(payload.get("y", 0))
        pyautogui.moveTo(x, y, duration=0.05)
        return jsonify({"status": "ok", "x": x, "y": y}), 200
    except Exception as e:
        logger.warning("api_cursor_move error: %s", e)
        return jsonify({"error": str(e)}), 400


@app.route("/api/cursor_click", methods=["POST"])
def api_cursor_click():
    """HTTP endpoint for cursor click (e.g. from main.py proxy)."""
    if not PYAUTOGUI_AVAILABLE:
        return jsonify({"error": "pyautogui not installed"}), 503
    payload = request.get_json(silent=True) or {}
    try:
        x = int(payload.get("x", 0))
        y = int(payload.get("y", 0))
        button = payload.get("button", "left")
        pyautogui.click(x, y, button=button)
        return jsonify({"status": "ok", "x": x, "y": y, "button": button}), 200
    except Exception as e:
        logger.warning("api_cursor_click error: %s", e)
        return jsonify({"error": str(e)}), 400


@app.route("/api/cursor/health", methods=["GET"])
def cursor_health():
    """Health check for cursor service."""
    return jsonify({"pyautogui_available": PYAUTOGUI_AVAILABLE}), 200


@socketio.on("cursor_click")
def on_cursor_click(data):
    """Click at (x, y). Expects { x: int, y: int, button?: "left"|"right" }."""
    if not PYAUTOGUI_AVAILABLE:
        emit("error", {"message": "pyautogui not installed"})
        return
    try:
        x = int(data.get("x", 0))
        y = int(data.get("y", 0))
        button = data.get("button", "left")
        pyautogui.click(x, y, button=button)
        emit("cursor_clicked", {"x": x, "y": y, "button": button})
    except Exception as e:
        logger.warning("cursor_click error: %s", e)
        emit("error", {"message": str(e)})


if __name__ == "__main__":
    logger.info("Cursor service on port %s", CURSOR_PORT)
    socketio.run(app, host="0.0.0.0", port=CURSOR_PORT, allow_unsafe_werkzeug=True)
