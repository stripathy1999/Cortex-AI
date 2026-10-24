# Vision-Driven Mirror Agent — Integration Plan

*How to add gesture-to-coordinate mapping and low-latency cursor control without breaking existing FaceTimeOS code.*

---

## Current Architecture (What We're Preserving)

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│  iMessage   │────▶│   main.py    │◀────│  call.py    │
│   Bridge    │     │  (Flask)     │     │ (FaceTime   │
└─────────────┘     │  Port 8003   │     │  audio)     │
                    └──────┬───────┘     └─────────────┘
                           │
                    ┌──────▼───────┐     ┌─────────────┐
                    │   Agent-S   │     │  Frontend   │
                    │  (LLM +     │     │  (Electron) │
                    │  PyAutoGUI) │     │  Port 8002  │
                    └─────────────┘     └─────────────┘
```

**Existing flows we keep intact:**
- Voice: FaceTime audio → call.py → main.py → Agent-S → TTS back
- Text: iMessage / UI prompt → main.py → Agent-S
- Screenshots: Agent-S uses `pyautogui.screenshot()` in its loop

---

## Integration Strategy: Additive Modules

Add new components as **optional services** that plug into the existing pipeline. If they're not running, the system behaves exactly as before.

---

## 1. Vision Service (New: `backend/vision_service.py`)

**Purpose:** Receive FaceTime video frames, run MediaPipe hand detection, map finger → screen coordinates.

**Design:**
- New Flask + Socket.IO server (e.g., port 5003)
- Accepts video frames via WebSocket or HTTP multipart
- Runs MediaPipe Hands for finger-tip detection
- Outputs `{ x, y }` in screen coordinates

**Video source options:**
| Option | How | Pros | Cons |
|-------|-----|------|------|
| A. Screen capture of FaceTime window | `screencapture` or `pyautogui` of the FaceTime app | No extra hardware | Need to identify FaceTime window; video is what Mac shows |
| B. BlackHole + virtual camera | Route FaceTime video to a virtual camera, capture via OpenCV | Direct video stream | More setup |
| C. Separate iOS app | Build a simple app that streams camera to your backend | Full control | Requires iOS dev |

**Recommended for MVP:** Option A — capture the FaceTime window (where you see yourself) using the same screen-capture path Agent-S already uses, but crop to the FaceTime video region.

**Key code structure:**
```python
# vision_service.py (new file)
# - /api/vision/frame — POST multipart image
# - Returns { "finger": { "x": 0.5, "y": 0.3 }, "confidence": 0.9 }
# - Uses mediapipe for hand landmarks
```

**Dependencies to add:** `mediapipe`, `opencv-python` (or `opencv-python-headless`)

---

## 2. Gesture-to-Coordinate Mapping

**The hard part:** Converting (finger_x, finger_y) in the video frame to (screen_x, screen_y).

**Approach:**
1. **Calibration step:** User holds phone at a fixed position, taps 4 corners of the Mac screen. Store the homography or perspective transform.
2. **Runtime:** Apply the transform to each finger position.
3. **Fallback:** Simple linear mapping (assume phone camera sees a rectangle that maps to screen).

**Where it lives:** Inside `vision_service.py` as a `CoordinateMapper` class. Load calibration from a JSON file (e.g. `~/.facetimeos/calibration.json`).

**Formula (simplified):**
```
screen_x = a * finger_x + b * finger_y + c
screen_y = d * finger_x + e * finger_y + f
```
(Full perspective: 3x3 homography matrix.)

---

## 3. Low-Latency Cursor Channel (Socket.IO)

**Purpose:** When the user points, the cursor moves in &lt;100ms without waiting for the full Agent-S loop.

**Design:**
- **New Socket.IO event** in `call.py` or a small **cursor_service.py** (port 5004):
  - Event: `cursor_move` with `{ x, y }`
- **Subscriber:** A lightweight client (could be in the frontend Electron app or a small Python script) that:
  - Listens for `cursor_move`
  - Calls `pyautogui.moveTo(x, y)` immediately

**Why not put it in main.py?** main.py is request/response. Cursor movement needs a persistent WebSocket. Reuse the same Socket.IO pattern as call.py.

**Flow:**
```
vision_service.py  ──(x,y)──▶  cursor_service.py  ──Socket.IO──▶  Cursor Client  ──▶  pyautogui.moveTo()
```

**Alternative:** Add a `cursor_move` event to `call.py` itself (it already has Socket.IO). Then vision_service just POSTs to main.py, which emits to call.py's Socket.IO. That keeps everything in one place.

---

## 4. Siri / Apple Shortcuts Trigger

**Purpose:** "Siri, tell Shadow to help me" → captures screenshot + voice snippet → sends to Claude.

**Implementation:**
1. Create an Apple Shortcut that:
   - Runs a shell script or calls a URL
   - Example: `curl -X POST http://localhost:8003/api/shadow_trigger -F "voice=@recording.m4a" -F "screenshot=@screen.png"`
2. Add **new endpoint** in main.py: `POST /api/shadow_trigger`
   - Accepts multipart: voice file + optional screenshot
   - Transcribes voice (reuse `audio.transcribe_audio_bytes`)
   - Combines with screenshot, forwards to Agent-S as a multimodal prompt

**No changes to existing endpoints.** This is purely additive.

---

## 5. "Mirror" Click Action

**Current:** Agent-S uses PyAutoGUI for clicks. It gets coordinates from the LLM (grounding model) based on screenshots.

**New:** When the user *points* at the screen, we already have (x, y) from the vision pipeline. We can:
- **Option A:** Emit `cursor_move` for real-time feedback, and on a "point-and-hold" or voice "click", send `cursor_click` with the same (x, y).
- **Option B:** Feed (x, y) into Agent-S as a hint: "User pointed at (x, y)" so the LLM can refine the click location.

**Recommended:** Option A for latency. Add `cursor_click` event that triggers `pyautogui.click(x, y)`.

---

## 6. Stagehand (Optional)

Stagehand is for browser/OS automation. Agent-S already does this with PyAutoGUI + grounding. You can:
- **Skip Stagehand** for now and keep Agent-S as-is.
- **Or** use Stagehand later for browser-specific tasks (e.g., "click the Add to Cart button") while keeping PyAutoGUI for general OS control.

---

## File Layout (Additive)

```
Treehacks/
├── backend/
│   ├── main.py              # ADD: /api/shadow_trigger, /api/cursor_move (or proxy to cursor service)
│   ├── call.py              # OPTIONAL: add cursor_move emit to existing Socket.IO
│   ├── vision_service.py    # NEW: MediaPipe + coordinate mapping
│   └── cursor_service.py    # NEW (optional): dedicated cursor WebSocket server
├── Agent-S/                 # No changes for basic integration
└── frontend/                # ADD: optional cursor client, Shadow trigger UI
```

---

## Implementation Order

| Phase | Task | Breaks existing? |
|-------|------|------------------|
| 1 | Add `vision_service.py` with MediaPipe hand detection | No |
| 2 | Add calibration + coordinate mapping | No |
| 3 | Add `cursor_service.py` or extend call.py with `cursor_move` | No |
| 4 | Connect vision_service → cursor_service | No |
| 5 | Add `/api/shadow_trigger` in main.py | No |
| 6 | Create Apple Shortcut for Siri trigger | No |
| 7 | Add "point-and-hold" or voice "click" for cursor_click | No |

---

## Environment Flags (Feature Toggles)

Add to `.env`:
```
ENABLE_VISION_MIRROR=false   # Set true to run vision + cursor pipeline
VISION_SERVICE_PORT=5003
CURSOR_SERVICE_PORT=5004
```

In `run.sh`, only start `vision_service.py` and `cursor_service.py` when `ENABLE_VISION_MIRROR=true`. This keeps the default run identical to today.

---

## Summary

- **Vision:** New `vision_service.py` — MediaPipe on video frames, outputs finger (x,y).
- **Mapping:** Calibration step + homography in vision_service.
- **Cursor:** New Socket.IO `cursor_move` / `cursor_click` — separate service or extend call.py.
- **Siri:** New `/api/shadow_trigger` in main.py, Apple Shortcut calls it.
- **Agent-S:** Unchanged. Optional: pass "user pointed at (x,y)" as context.
- **Feature flag:** `ENABLE_VISION_MIRROR` so nothing runs unless you opt in.

All changes are additive; existing voice, iMessage, and UI flows stay intact.
