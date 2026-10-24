#!/usr/bin/env python3
"""
Vision-Driven Mirror Agent — Hand/finger detection and coordinate mapping.

Receives video frames (e.g., from FaceTime window capture), runs MediaPipe
for hand landmarks, maps finger position to screen coordinates.

Start only when ENABLE_VISION_MIRROR=true. Does not affect existing services.
"""
from __future__ import annotations

import base64
import io
import json
import logging
import os
from pathlib import Path

from flask import Flask, request, jsonify
from flask_cors import CORS

# Optional: mediapipe + opencv. Install with: uv add mediapipe opencv-python-headless numpy
try:
    import numpy as np
    import cv2
    import mediapipe as mp
    VISION_AVAILABLE = True
except ImportError:
    VISION_AVAILABLE = False
    np = None

CALIBRATION_PATH = Path.home() / ".facetimeos" / "calibration.json"
VISION_PORT = int(os.getenv("VISION_SERVICE_PORT", "5003"))

app = Flask(__name__)
CORS(app)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CoordinateMapper:
    """Maps (finger_x, finger_y) in video frame to (screen_x, screen_y)."""

    def __init__(self):
        self.matrix = None  # 3x3 homography or affine params
        self.screen_width = 1920
        self.screen_height = 1080
        self._load_calibration()

    def _load_calibration(self):
        if CALIBRATION_PATH.exists():
            try:
                with open(CALIBRATION_PATH) as f:
                    data = json.load(f)
                self.matrix = data.get("matrix")
                self.screen_width = data.get("screen_width", 1920)
                self.screen_height = data.get("screen_height", 1080)
            except Exception as e:
                logger.warning("Could not load calibration: %s", e)

    def map(self, norm_x: float, norm_y: float) -> tuple[float, float]:
        """Map normalized (0-1) finger position to screen coords."""
        if self.matrix:
            # TODO: Apply homography
            pass
        # Fallback: linear mapping
        return (
            norm_x * self.screen_width,
            norm_y * self.screen_height,
        )


mapper = CoordinateMapper()
mp_hands = mp.solutions.hands.Hands(static_image_mode=False, max_num_hands=1) if VISION_AVAILABLE else None


def detect_finger_tip(image_bytes: bytes) -> dict | None:
    """Run MediaPipe on image, return finger tip in normalized coords or None."""
    if not VISION_AVAILABLE or mp_hands is None:
        return None

    arr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        return None

    rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    results = mp_hands.process(rgb)

    if not results.multi_hand_landmarks:
        return None

    # Index finger tip = landmark 8
    landmarks = results.multi_hand_landmarks[0].landmark
    tip = landmarks[8]
    return {"x": tip.x, "y": tip.y, "confidence": 0.9}


@app.route("/api/vision/frame", methods=["POST"])
def process_frame():
    """Accept base64 image or multipart file, return finger position in screen coords."""
    if not VISION_AVAILABLE:
        return jsonify({"error": "mediapipe/opencv not installed"}), 503

    image_bytes = None
    if request.content_type and "multipart" in request.content_type:
        f = request.files.get("image") or request.files.get("frame")
        if f:
            image_bytes = f.read()
    else:
        payload = request.get_json(silent=True) or {}
        b64 = payload.get("image") or payload.get("frame")
        if b64:
            image_bytes = base64.b64decode(b64)

    if not image_bytes:
        return jsonify({"error": "No image provided"}), 400

    finger = detect_finger_tip(image_bytes)
    if finger is None:
        return jsonify({"finger": None, "message": "No hand detected"}), 200

    screen_x, screen_y = mapper.map(finger["x"], finger["y"])
    return jsonify({
        "finger": {"x": finger["x"], "y": finger["y"], "confidence": finger["confidence"]},
        "screen": {"x": int(screen_x), "y": int(screen_y)},
    }), 200


@app.route("/api/vision/calibrate", methods=["POST"])
def save_calibration():
    """Save calibration data (e.g., after 4-point calibration)."""
    payload = request.get_json(silent=True) or {}
    CALIBRATION_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CALIBRATION_PATH, "w") as f:
        json.dump(payload, f, indent=2)
    mapper._load_calibration()
    return jsonify({"status": "ok"}), 200


@app.route("/api/vision/health", methods=["GET"])
def health():
    return jsonify({"vision_available": VISION_AVAILABLE}), 200


if __name__ == "__main__":
    logger.info("Vision service on port %s (vision_available=%s)", VISION_PORT, VISION_AVAILABLE)
    app.run(host="0.0.0.0", port=VISION_PORT)
