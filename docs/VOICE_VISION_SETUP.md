# Voice + Vision Mode Setup

Use your **voice** and **finger pointing** instead of typing.

## What's New

- **Voice:** Click the mic button, speak your command, and it's sent to the agent
- **Vision:** Click the camera button, show your hand to the webcam, and your finger position controls the cursor in real time

## Prerequisites

1. **Backend, Agent-S, Frontend** — already running
2. **Vision service** — for finger tracking (requires MediaPipe)
3. **Cursor service** — for moving the mouse

## Start Vision + Cursor Services

**Terminal 4 — Vision service:**
```powershell
cd Treehacks\backend
uv run vision_service.py
```

**Terminal 5 — Cursor service:**
```powershell
cd Treehacks\backend
uv run cursor_service.py
```

## Install Vision Dependencies (if needed)

If vision_service returns "mediapipe/opencv not installed":

```powershell
cd Treehacks\backend
uv add ".[vision]"
```

## How to Use

1. **Voice:** Click the microphone icon → speak (e.g. "Open Notepad") → your speech is sent as a prompt
2. **Vision:** Click the camera icon → a small webcam preview appears → point your finger at the screen → the cursor follows your finger

## Troubleshooting

- **Voice not working:** Web Speech API requires Chrome/Chromium (Electron uses it). Ensure mic permission is granted.
- **Vision 503:** Start vision_service and install `.[vision]` deps
- **Cursor not moving:** Start cursor_service; ensure pyautogui is installed
