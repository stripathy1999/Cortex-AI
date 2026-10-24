# Task Division: Windows vs Mac

*How to split work so you (Windows) and your friend (Mac) can develop in parallel, test independently, and merge via GitHub.*

---

## Quick Reference

| You (Windows) | Friend (Mac) |
|---------------|--------------|
| Frontend (Electron) | iMessage bridge |
| Vision service | call.py (FaceTime audio) |
| Cursor service | Full run.sh + E2E testing |
| Agent-S (with Windows fallbacks) | Apple Shortcuts + Siri |
| New API endpoints (logic) | main.py screenshot (screencapture) |
| Documentation | BlackHole + FaceTime setup |

---

## YOUR TASKS (Windows) — Fully Testable

### 1. Frontend (Electron UI)

**Location:** `frontend/`

**What you can do:**
- Build and run: `cd frontend && npm install && npm start`
- Add UI for Vision Mirror mode (toggle, calibration button)
- Add Shadow trigger button (calls `/api/shadow_trigger`)
- Improve Queue, Solutions, Debug pages
- Add Socket.IO client for real-time cursor preview (optional)

**Test:** App launches, UI works, you can send prompts via the command bar.

---

### 2. Vision Service

**Location:** `backend/vision_service.py`

**What you can do:**
- Finish MediaPipe hand detection (skeleton exists)
- Implement `CoordinateMapper` with calibration JSON
- Add 4-point calibration API
- Accept frames from webcam (for testing: use your laptop webcam instead of FaceTime)

**Test on Windows:**
```powershell
cd backend
uv add ".[vision]"
uv run vision_service.py
# In another terminal, POST a test image:
# curl -X POST http://localhost:5003/api/vision/frame -F "image=@test_hand.png"
```

---

### 3. Cursor Service

**Location:** `backend/cursor_service.py`

**What you can do:**
- Run and test: `uv run cursor_service.py`
- Add a simple test client (Python or Node) that emits `cursor_move` and verifies the cursor moves

**Test on Windows:**
```powershell
cd backend
uv run cursor_service.py
# Use a small Python script to emit cursor_move via socketio and watch your mouse move
```

---

### 4. Agent-S (Windows Compatibility)

**Location:** `Agent-S/`

**What you can do:**
- Agent-S has `pywinauto` and `pywin32` for Windows — it should run
- Fix any Windows-specific bugs (e.g. `LocalController` uses `/bin/bash` — add a fallback for Windows `cmd` or PowerShell)
- Test the full Agent-S loop: prompt → screenshot → LLM → action

**Test on Windows:**
```powershell
cd Agent-S
$env:ANTHROPIC_API_KEY = "your-key"
uv run -m src.s3.app --provider anthropic --model claude-sonnet-4-20250514 ...
```

---

### 5. Backend main.py — New Endpoints (No Mac Logic)

**Location:** `backend/main.py`

**What you can do:**
- Add `POST /api/shadow_trigger` — accepts multipart (voice + screenshot), transcribes, forwards to Agent-S
- Add `POST /api/vision/cursor_move` — proxy to cursor_service (or emit directly)
- Make these endpoints **optional** — if cursor_service or vision_service isn’t running, return a clear error

**Test on Windows:**
```powershell
# Start main.py (without imessage_bridge, call.py)
cd backend
uv run main.py
# curl -X POST http://localhost:8003/api/shadow_trigger -F "voice=@test.wav"
```

---

### 6. Cross-Platform Screenshot in main.py

**Location:** `backend/main.py` — `capture_screenshot()`

**What you can do:**
- Add a Windows path using `mss` or `pyautogui.screenshot()`:
  ```python
  if sys.platform == "darwin":
      subprocess.run(["screencapture", "-x", str(temp_path)], check=True)
  else:
      import mss
      with mss.mss() as sct:
          sct.shot(output=str(temp_path))
  ```
- This lets `main.py` run on Windows for your `/api/completetask` testing (you can mock the iMessage part).

---

### 7. Vision → Cursor Bridge Script

**Location:** `backend/vision_cursor_bridge.py` (new)

**What you can do:**
- Small script that:
  1. Polls vision_service for finger position (or receives via WebSocket)
  2. Emits `cursor_move` to cursor_service
- Run on Windows with webcam + vision_service + cursor_service to test the full gesture pipeline.

---

### 8. Documentation

**Location:** `docs/`, `README.md`

**What you can do:**
- Windows setup instructions
- API docs for new endpoints
- Troubleshooting for Vision Mirror

---

## FRIEND'S TASKS (Mac) — macOS-Only

### 1. iMessage Bridge

**Location:** `backend/imessage_bridge.py`

**What they do:**
- Poll `~/Library/Messages/chat.db`
- Use `imessage` CLI (`brew install imessage-ruby`) to send replies
- Any changes to forwarding logic, contact filtering, etc.

**Test:** Only on Mac with real iMessage.

---

### 2. call.py (FaceTime Audio)

**Location:** `backend/call.py`

**What they do:**
- BlackHole setup, audio device config
- VAD tuning, utterance handling
- Any changes to Socket.IO events for FaceTime

**Test:** Only on Mac with FaceTime + BlackHole.

---

### 3. main.py — Mac-Specific Parts

**Location:** `backend/main.py`

**What they do:**
- Keep `screencapture` for `capture_screenshot()` on Mac (you add the Windows branch)
- Test `/api/completetask` with real iMessage
- Test full flow: FaceTime voice → call.py → main.py → Agent-S → TTS

---

### 4. Apple Shortcuts + Siri

**What they do:**
- Create Shortcut: "Tell Shadow to help me" → runs script that POSTs to `http://localhost:8003/api/shadow_trigger`
- Capture screenshot + voice, send to backend
- Test Siri integration

---

### 5. run.sh and Full E2E

**What they do:**
- Maintain `run.sh` (bash)
- Test full stack: `./run.sh` → FaceTime + iMessage + Agent-S + Frontend
- Fix any Mac-specific issues

---

### 6. FaceTime Video Capture (for Vision)

**What they do:**
- Implement capture of FaceTime window (where user sees themselves)
- Send frames to vision_service (you build vision_service; they build the capture + pipe)
- Option: use `screencapture` with window region, or BlackHole + virtual camera

---

## GitHub Workflow

### Branch Strategy

- **main** — stable, merged from both
- **windows/** — your branch (e.g. `windows/vision-cursor`)
- **mac/** — friend’s branch (e.g. `mac/imessage-facetime`)

### Merge Order

1. You merge `windows/vision-cursor` → main (vision, cursor, frontend, new endpoints)
2. Friend merges `mac/imessage-facetime` → main (call.py, imessage, run.sh)
3. Resolve conflicts in `main.py` — your Windows screenshot + their screencapture

### Avoiding Conflicts

- **main.py:** You add new routes and Windows branches; they don’t touch those
- **.env:** Use `.env.example` with placeholders; each dev has local `.env`
- **run.sh:** They own it; you can add a `run_windows.ps1` or `run_windows.bat` for your stack

---

## What You Can Test End-to-End on Windows

| Flow | Testable? | How |
|------|-----------|-----|
| Frontend → main.py → Agent-S | ✅ | Start main.py + Agent-S, use UI to send prompt |
| Vision service (hand detection) | ✅ | Webcam or test image → POST to vision_service |
| Cursor service | ✅ | Emit cursor_move → mouse moves |
| Vision → Cursor pipeline | ✅ | Webcam → vision_service → bridge → cursor_service |
| Shadow trigger (voice + screenshot) | ✅ | curl with test files; mock iMessage |
| iMessage / FaceTime | ❌ | Mac only |

---

## Summary

**You (Windows):** Frontend, Vision, Cursor, new API endpoints, Agent-S Windows fixes, cross-platform screenshot, docs. All testable on your machine.

**Friend (Mac):** iMessage, call.py, FaceTime, Apple Shortcuts, run.sh, full E2E, FaceTime video capture.

**Sync:** Merge via GitHub; coordinate on `main.py` and `.env` to avoid conflicts.
