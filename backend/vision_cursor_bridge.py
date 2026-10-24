#!/usr/bin/env python3
"""
Vision → Cursor Bridge for Shadow-OS.

Captures frames from webcam (or another source), sends to vision_service
for finger detection, emits cursor_move to cursor_service.

Run with:
  uv run vision_cursor_bridge.py

Requires: vision_service and cursor_service to be running.
Optional: uv add ".[vision]" for opencv (webcam capture).
"""
from __future__ import annotations

import logging
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

VISION_URL = os.getenv("VISION_SERVICE_URL", "http://localhost:5003")
CURSOR_URL = os.getenv("CURSOR_SERVICE_URL", "http://localhost:5004")
POLL_INTERVAL_MS = int(os.getenv("VISION_POLL_INTERVAL_MS", "50"))
MIN_CONFIDENCE = float(os.getenv("VISION_MIN_CONFIDENCE", "0.7"))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def run_webcam_bridge() -> None:
    """Capture webcam frames, send to vision, emit to cursor."""
    try:
        import cv2
        import requests
        import socketio
    except ImportError as e:
        logger.error("Need: uv add '.[vision]' and pip install python-socketio[client] requests")
        raise SystemExit(1) from e

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        logger.error("Could not open webcam")
        raise SystemExit(1)

    sio = socketio.Client(logger=False, engineio_logger=False)
    try:
        sio.connect(CURSOR_URL, wait_timeout=5)
    except Exception as e:
        logger.error("Could not connect to cursor service at %s: %s", CURSOR_URL, e)
        cap.release()
        raise SystemExit(1) from e

    interval_sec = POLL_INTERVAL_MS / 1000.0
    logger.info("Bridge running: webcam -> vision -> cursor (interval=%.0fms)", POLL_INTERVAL_MS)

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            _, buf = cv2.imencode(".jpg", frame)
            data = buf.tobytes()

            try:
                r = requests.post(
                    f"{VISION_URL}/api/vision/frame",
                    files={"image": ("frame.jpg", data, "image/jpeg")},
                    timeout=0.5,
                )
                if r.status_code == 200:
                    j = r.json()
                    finger = j.get("finger")
                    if finger and finger.get("confidence", 0) >= MIN_CONFIDENCE:
                        screen = j.get("screen", {})
                        x, y = screen.get("x", 0), screen.get("y", 0)
                        sio.emit("cursor_move", {"x": x, "y": y})
            except requests.RequestException:
                pass
            except Exception as e:
                logger.debug("Vision request error: %s", e)

            time.sleep(interval_sec)

    except KeyboardInterrupt:
        logger.info("Stopped by user")
    finally:
        cap.release()
        sio.disconnect()


if __name__ == "__main__":
    run_webcam_bridge()
