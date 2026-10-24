# Video Call Feature: FaceTime, Zoom, Google Meet, WhatsApp

Message your PC **"video call me"** or **"FaceTime me"** and the agent picks the most efficient option and performs the action.

## How It Works

1. You send: **"video call me"**, **"FaceTime me"**, or **"start a video call"**
2. The agent checks: **FaceTime (Mac + iMessage)**, WhatsApp (direct call), Zoom (API), Google Meet
3. **Smart choice**: FaceTime (iMessage) or WhatsApp → direct call (no link, rings immediately). Zoom/Meet → meeting link.
4. During the call, say **"share screen"** to share your screen
5. Voice commands: only **tasks** are executed; filler words and casual chat are ignored

## Platform Priority (Most Efficient First)

| Priority | Platform | When | Result |
|----------|----------|------|--------|
| 1 | **FaceTime** | macOS + you messaged from iMessage (phone or Apple ID) | **Direct call** – FaceTime opens and rings you |
| 2 | **WhatsApp** | Installed + you messaged from WhatsApp | **Direct call** – rings your phone, no link |
| 3 | **Zoom** | API credentials in `.env` | Meeting link |
| 4 | **Google Meet** | Stagehand or browser | Meeting link |

## FaceTime (macOS, iMessage)

**Detailed setup (phone number vs iCloud email, vision vs AppleScript, .env, CLI):** see **[FACETIME_SETUP.md](FACETIME_SETUP.md)**.

When you message from **iMessage** on a **Mac** and say **"FaceTime me"** or **"video call me"**:

1. The backend opens `facetime://` with your number or Apple ID (from the message sender).
2. FaceTime launches and places the call to you – answer on your iPhone/iPad/Mac.
3. The call service (`call.py`) starts so **voice commands work during the call** (requires BlackHole or similar for audio routing on Mac).

**Requirements**: macOS, FaceTime installed, and message from iMessage so we have your phone number or Apple ID.

## Zoom Setup (Recommended)

1. Create a [Zoom Server-to-Server OAuth app](https://marketplace.zoom.us/) at Zoom Marketplace
2. Add scopes: `meeting:write:meeting:admin`, `meeting:read:meeting:admin`
3. Add to `.env`:

```
ZOOM_ACCOUNT_ID=your-account-id
ZOOM_CLIENT_ID=your-client-id
ZOOM_CLIENT_SECRET=your-client-secret
```

4. Restart the backend. The agent will create instant meetings via the Zoom API.

## WhatsApp Direct Call (Preferred When Available)

When you message from **WhatsApp** and WhatsApp Desktop is installed, the agent will:
1. Open WhatsApp Desktop
2. Search for your contact
3. Click the video call button
4. Your phone rings – no link to open

**Requirement**: Message "video call me" from WhatsApp (so we have your number). The agent prefers this over Zoom/Meet when available because it's more efficient.

## Google Meet (Fallback)

- **With Stagehand**: Ensure Stagehand service is running. It will open Chrome and create a Meet.
- **Without Stagehand**: The service opens your default browser at `meet.google.com/new` and extracts the URL.

## Screen Share During Call

When you're in a Zoom/Meet call and say **"share screen"** or **"share my screen"**:

- The agent uses the **Alt+S** shortcut (Zoom) to trigger screen share
- Your voice is captured by the call service (requires VB-Audio Cable or similar for full audio routing)

## Voice Commands During Call

1. **Call service** (`call.py`) must be running
2. **VB-Audio Cable** (or similar): Route Zoom/Meet output to an input device that `call.py` captures
3. Say commands like "share screen", "open Notepad", "search Google for X"
4. The agent **only executes clear tasks** – filler words (um, uh, like), greetings (hi, hello), and casual chat are ignored

## Testing

Run the test suite from `backend/`:

```powershell
cd Treehacks\backend
uv run python test_video_call.py
```

This tests: detection, options, routing, and (if backend is running) the live API.

## Debugging

- **Check options**: `GET http://localhost:8003/api/video_call_options`
- **Logs**: Backend logs show which platform was chosen and why

## Troubleshooting

| Issue | Fix |
|-------|-----|
| "No video call option available" | Install Zoom, add API credentials, or ensure Stagehand is running |
| Zoom API fails | Verify `ZOOM_ACCOUNT_ID`, `ZOOM_CLIENT_ID`, `ZOOM_CLIENT_SECRET` |
| Meet URL not extracted | Ensure Chrome is focused; try again in browser; check Stagehand |
| Voice not heard | Run `call.py`; configure VB-Audio Cable or similar for audio routing |
