#!/usr/bin/env python3
"""
Test script for Vision Service and Cursor Service.

Usage:
  1. Start vision_service:  uv run vision_service.py
  2. Start cursor_service: uv run cursor_service.py
  3. Run this script:      uv run test_vision_cursor.py

Or test individually:
  uv run test_vision_cursor.py --vision-only    # Test vision with webcam or image
  uv run test_vision_cursor.py --cursor-only   # Test cursor movement
"""
from __future__ import annotations

import argparse
import base64
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).resolve().parent))

VISION_URL = "http://localhost:5003"
CURSOR_URL = "http://localhost:5004"


def test_vision_with_image(image_path: str) -> None:
    """POST an image to vision service, print finger/screen coords."""
    import requests

    path = Path(image_path)
    if not path.exists():
        print(f"Image not found: {path}")
        return

    with open(path, "rb") as f:
        data = f.read()

    print(f"POSTing {len(data)} bytes to {VISION_URL}/api/vision/frame ...")
    r = requests.post(
        f"{VISION_URL}/api/vision/frame",
        files={"image": (path.name, data, "image/png")},
        timeout=10,
    )

    if r.status_code != 200:
        print(f"Error {r.status_code}: {r.text}")
        return

    j = r.json()
    if j.get("finger") is None:
        print("No hand detected in image.")
        return

    print(f"Finger (normalized): x={j['finger']['x']:.3f}, y={j['finger']['y']:.3f}")
    print(f"Screen coords: x={j['screen']['x']}, y={j['screen']['y']}")


def test_vision_with_webcam() -> None:
    """Capture from webcam, send to vision service in a loop."""
    try:
        import cv2
        import requests
    except ImportError:
        print("Need: pip install opencv-python requests")
        return

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Could not open webcam")
        return

    print("Press 'q' to quit. Showing webcam + sending frames to vision service...")
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
                timeout=1,
            )
            if r.status_code == 200:
                j = r.json()
                if j.get("finger"):
                    x, y = j["screen"]["x"], j["screen"]["y"]
                    cv2.circle(frame, (int(j["finger"]["x"] * frame.shape[1]), int(j["finger"]["y"] * frame.shape[0])), 10, (0, 255, 0), 2)
                    cv2.putText(frame, f"Screen: ({x},{y})", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        except Exception as e:
            pass  # Vision service might not be running

        cv2.imshow("Vision Test", frame)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()


def test_cursor_move() -> None:
    """Connect to cursor service via Socket.IO and move mouse."""
    import time
    try:
        import socketio
    except ImportError:
        print("Need: pip install python-socketio[client]")
        return

    sio = socketio.Client()

    @sio.on("connect")
    def on_connect():
        print("Connected to cursor service. Moving mouse in a square...")
        # Move in a 100x100 square
        for x, y in [(400, 300), (500, 300), (500, 400), (400, 400), (400, 300)]:
            sio.emit("cursor_move", {"x": x, "y": y})
            time.sleep(0.3)

    @sio.on("cursor_moved")
    def on_moved(data):
        print(f"  Cursor moved to ({data['x']}, {data['y']})")

    try:
        sio.connect("http://127.0.0.1:5004", wait_timeout=5)
        time.sleep(1.5)  # Wait for square to complete
        sio.disconnect()
        print("Done. Did you see the mouse move?")
    except Exception as e:
        print(f"Could not connect to cursor service: {e}")
        print("Make sure cursor_service is running: uv run cursor_service.py")


def test_cursor_click() -> None:
    """Connect and perform a click at center of screen."""
    import time
    try:
        import socketio
    except ImportError:
        print("Need: pip install python-socketio[client]")
        return

    sio = socketio.Client()
    import pyautogui
    w, h = pyautogui.size()
    cx, cy = w // 2, h // 2

    @sio.on("connect")
    def on_connect():
        print(f"Clicking at center ({cx}, {cy})...")
        sio.emit("cursor_click", {"x": cx, "y": cy, "button": "left"})

    @sio.on("cursor_clicked")
    def on_clicked(data):
        print(f"  Clicked at ({data['x']}, {data['y']})")
        sio.disconnect()

    try:
        sio.connect("http://127.0.0.1:5004", wait_timeout=5)
        time.sleep(1)
    except Exception as e:
        print(f"Could not connect: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--vision-only", action="store_true", help="Test vision service with webcam")
    parser.add_argument("--vision-image", type=str, help="Test vision with image file path")
    parser.add_argument("--cursor-only", action="store_true", help="Test cursor service (move in square)")
    parser.add_argument("--cursor-click", action="store_true", help="Test cursor click")
    args = parser.parse_args()

    if args.vision_image:
        test_vision_with_image(args.vision_image)
    elif args.vision_only:
        test_vision_with_webcam()
    elif args.cursor_click:
        test_cursor_click()
    elif args.cursor_only:
        test_cursor_move()
    else:
        print(__doc__)
        print("\nExamples:")
        print("  uv run test_vision_cursor.py --vision-image hand.png")
        print("  uv run test_vision_cursor.py --vision-only")
        print("  uv run test_vision_cursor.py --cursor-only")
