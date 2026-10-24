# How Vision Service & Cursor Service Work

A step-by-step explanation of the gesture-to-cursor pipeline.

---

## Vision Service (Port 5003)

### What It Does

1. **Receives** an image (video frame) — e.g. from FaceTime, webcam, or a test image
2. **Runs MediaPipe** to detect hand landmarks (21 points per hand)
3. **Extracts** the index finger tip (landmark #8)
4. **Maps** normalized (0–1) finger position → screen coordinates (pixels)
5. **Returns** `{ finger: {x, y}, screen: {x, y} }`

### Flow

```
┌─────────────────┐     POST /api/vision/frame      ┌──────────────────┐
│  Image source   │ ──────────────────────────────▶│  Vision Service  │
│  (webcam,      │     (multipart or base64)       │  (Flask, :5003)  │
│   FaceTime,    │                                 │                  │
│   test image)  │◀────────────────────────────────│  MediaPipe Hands │
└─────────────────┘     { finger, screen }         │  → finger tip    │
                                                    │  → CoordinateMapper
                                                    └──────────────────┘
```

### API

| Endpoint | Method | Input | Output |
|----------|--------|-------|--------|
| `/api/vision/frame` | POST | `image` (file) or `frame` (base64) | `{ finger: {x, y, confidence}, screen: {x, y} }` |
| `/api/vision/calibrate` | POST | `{ matrix, screen_width, screen_height }` | Saves to `~/.facetimeos/calibration.json` |
| `/api/vision/health` | GET | — | `{ vision_available: true/false }` |

### Coordinate Mapping

- **MediaPipe** returns `x`, `y` in **normalized** coords (0–1, origin top-left)
- **CoordinateMapper** converts to screen pixels:
  - Without calibration: `screen_x = x * screen_width`, `screen_y = y * screen_height`
  - With calibration: use homography matrix (perspective transform) for accurate mapping when camera is at an angle

---

## Cursor Service (Port 5004)

### What It Does

1. **Listens** for Socket.IO events over WebSocket
2. **On `cursor_move`:** calls `pyautogui.moveTo(x, y)` immediately
3. **On `cursor_click`:** calls `pyautogui.click(x, y)` 
4. **Emits** confirmation events back (`cursor_moved`, `cursor_clicked`)

### Flow

```
┌─────────────────┐     Socket.IO (WebSocket)      ┌──────────────────┐
│  Client         │ ──────────────────────────────▶│  Cursor Service  │
│  (vision bridge,│     emit("cursor_move",        │  (Flask-SocketIO,│
│   test script)  │      {x: 500, y: 300})        │     :5004)       │
│                 │                                │                  │
│                 │◀───────────────────────────────│  pyautogui       │
│                 │     emit("cursor_moved", ...)  │  .moveTo(x,y)    │
└─────────────────┘                                └──────────────────┘
                                                             │
                                                             ▼
                                                    ┌──────────────────┐
                                                    │  Your mouse      │
                                                    │  moves!          │
                                                    └──────────────────┘
```

### Events

| Event (client → server) | Payload | Server action |
|-------------------------|---------|---------------|
| `cursor_move` | `{ x: int, y: int }` | `pyautogui.moveTo(x, y)` |
| `cursor_click` | `{ x: int, y: int, button?: "left"\|"right" }` | `pyautogui.click(x, y, button)` |

| Event (server → client) | Payload |
|------------------------|---------|
| `cursor_moved` | `{ x, y }` |
| `cursor_clicked` | `{ x, y, button }` |

---

## Full Pipeline (Vision → Cursor)

When everything is connected:

```
FaceTime/Webcam  →  Vision Service  →  Bridge Script  →  Cursor Service  →  Mouse
     (frame)           (finger x,y)      (emit)            (moveTo)        (moves)
```

1. **Capture** a frame (e.g. every 50ms from webcam)
2. **POST** to `/api/vision/frame`
3. **Get** `screen: {x, y}` back
4. **Emit** `cursor_move` to cursor service with that `{x, y}`
5. **Mouse** moves to where you're pointing

---

## How to Test

### 1. Vision Service

```powershell
cd Treehacks/backend
uv add ".[vision]"
uv run vision_service.py
```

In another terminal:

```powershell
# With a hand image (PNG/JPG)
curl -X POST http://localhost:5003/api/vision/frame -F "image=@hand.png"

# Or use the test script with webcam
uv run test_vision_cursor.py --vision-only
```

### 2. Cursor Service

```powershell
cd Treehacks/backend
uv run cursor_service.py
```

In another terminal:

```powershell
# Test: mouse moves in a square
uv run test_vision_cursor.py --cursor-only

# Test: click at center of screen
uv run test_vision_cursor.py --cursor-click
```

### 3. Combined (Vision → Cursor)

Run both services, then:

```powershell
uv run test_vision_cursor.py --vision-only
```

With a small bridge script (to be added), the webcam feed would continuously send frames to vision, get coords, and emit to cursor — so your mouse follows your finger.
