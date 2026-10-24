# FaceTime Setup: Phone Number vs iCloud Email

How to make the **"FaceTime me"** flow work when you message your Mac from iMessage or trigger from the UI.

---

## How the system chooses who to call

| Source | Contact used | Example |
|--------|----------------|--------|
| **iMessage (sender has phone number)** | Sender’s phone number | You text from +1 555 555 0100 → Mac calls that number |
| **iMessage (sender is iCloud email)** | Sender’s Apple ID (email) | You text from `you@icloud.com` → Mac calls that Apple ID |
| **UI / no sender** | `.env` fallback | You click “video call” in the app → Mac uses `FACETIME_APPLE_ID` or `FACETIME_DEFAULT_NUMBER` |

So: **by number** = we use the message sender’s phone; **by iCloud email** = we use the sender’s Apple ID. No extra config needed for “FaceTime me” from iMessage as long as the bridge sends `phone_number` or a valid `source`.

---

## 1. FaceTime by **phone number**

### What you need

- **Mac**: FaceTime installed, signed in with your Apple ID.
- **Contact**: A phone number that can receive FaceTime (e.g. iPhone number with FaceTime enabled).

### .env (optional)

Used when there’s **no** sender (e.g. UI) or as fallback:

```bash
# Who to call when the request has no number (e.g. from UI)
FACETIME_DEFAULT_NUMBER="+15555550100"
```

For **10-digit US numbers** we automatically prepend `1`. For other countries, set:

```bash
# e.g. India
FACETIME_DEFAULT_COUNTRY_CODE=91
```

### Flow

1. You send **“FaceTime me”** from iMessage (from your iPhone number).
2. iMessage bridge sends that message to the backend with `phone_number` = your number (e.g. `+15555550100` or `iMessage;-;+15555550100`).
3. Backend opens `facetime://15555550100` (digits only, no `+`).
4. FaceTime opens; after a short delay we click the **Call / Video** button (vision first, then AppleScript).
5. Your iPhone rings; answer to start the call.

So FaceTime works **by number** as long as the bridge sends the sender’s number and the backend can normalize it (we strip `iMessage;-;` and add country code if needed).

---

## 2. FaceTime by **iCloud / Apple ID email**

### What you need

- **Mac**: FaceTime installed, signed in with an Apple ID.
- **Contact**: An Apple ID (email) that has FaceTime enabled (e.g. `friend@icloud.com`).

### .env (optional)

For UI or when there’s no sender:

```bash
# Fallback when no sender (e.g. “video call” from UI)
FACETIME_APPLE_ID=yourmac@icloud.com
```

If the **sender** is an iCloud email, the bridge sends that as `phone_number` or in the handle (e.g. `friend@icloud.com`). We use it as-is for `facetime://friend@icloud.com` — no country code.

### Flow

1. You send **“FaceTime me”** from iMessage signed in as `you@icloud.com`.
2. Bridge sends `phone_number` (or equivalent) = `you@icloud.com`.
3. Backend opens `facetime://you@icloud.com`.
4. FaceTime opens; we click Call/Video (vision or AppleScript).
5. Your device (Mac/iPhone/iPad with that Apple ID) rings.

So FaceTime works **by iCloud email** when the message source is that email and the bridge includes it in the payload.

---

## 3. Making the “Call” button work (vision vs AppleScript)

After opening `facetime://...`, the app must click the **Call** or **Video** button. We do that in two ways:

### A) Vision (Claude / grounding) – preferred

- **Agent-S** must be running (it provides the vision/grounding model).
- Backend calls `POST http://<Agent-S>/api/facetime_click_call`.
- Agent-S takes a screenshot, finds the Call/Video button with vision, and clicks it.
- Works across different macOS / FaceTime UI versions.

**Requirement**: Start Agent-S before using FaceTime (e.g. via `./run_order.sh`).

### B) AppleScript (accessibility) – fallback

- If Agent-S is not running or the vision call fails, we use AppleScript to activate FaceTime and press Return or click the button by name/accessibility.
- **Requirement**: Grant **Accessibility** to Terminal (or the app running the backend):  
  **System Settings → Privacy & Security → Accessibility** → enable Terminal (or your IDE/app).

So: **vision** = more reliable and layout-independent; **AppleScript** = works without Agent-S but needs Accessibility and may break if Apple changes the UI.

---

## 4. .env summary

| Variable | Purpose |
|----------|--------|
| `FACETIME_APPLE_ID` | Your Mac’s Apple ID (optional); fallback when there’s no sender (e.g. UI). |
| `FACETIME_DEFAULT_NUMBER` | Default phone to call when there’s no sender (e.g. UI). |
| `FACETIME_DEFAULT_COUNTRY_CODE` | Country code for 10-digit numbers (e.g. `91` for India). US defaults to `1` if unset. |
| `FACETIME_CALL_DELAY_SEC` | Seconds to wait after opening FaceTime before clicking Call (default `10`). |
| `AGENT_HOST` / `AGENT_PORT` | Used by the backend to call Agent-S for vision click (default `127.0.0.1:8005`). |

---

## 5. Testing from the CLI

1. **Start stack** (backend + Agent-S + iMessage bridge):

   ```bash
   ./run_order.sh
   ```

2. **Trigger from iMessage**  
   From your iPhone (or another Mac with iMessage), send **“FaceTime me”** to the Mac. The Mac should open FaceTime and place the call to you (by number or iCloud email, as above).

3. **Trigger from UI**  
   In the app, send a message like **“FaceTime me”** or **“video call me”**. The Mac will use `FACETIME_DEFAULT_NUMBER` or `FACETIME_APPLE_ID` from `.env` as the contact.

4. **Check video call options** (no call placed):

   ```bash
   curl "http://127.0.0.1:8003/api/video_call_options"
   ```

   Response includes `facetime_ready` and which contact source is available.

5. **Backend logs**  
   Look for lines like:
   - `FaceTime requested: contact=...`
   - `FaceTime: using contact ...`
   - `FaceTime: vision click succeeded` or `FaceTime: sent Return (start call)`

---

## 6. Troubleshooting

| Issue | What to do |
|-------|------------|
| **Call never starts (FaceTime opens, shows "Click to call", but no ring)** | The **Call** button at the bottom isn't being clicked. 1) Start Agent-S so vision can find and click it. 2) Grant **Accessibility** to Terminal: System Settings → Privacy & Security → Accessibility. 3) Increase `FACETIME_CALL_DELAY_SEC` (e.g. `12`). |
| **“Could not normalize contact”** | Sender’s handle must be a phone number (digits, optional `+`) or an email. Check bridge payload: `phone_number` / `source`. |
| **Wrong person is called** | For “FaceTime me” we use the **sender** first. Only with no sender do we use `FACETIME_DEFAULT_NUMBER` / `FACETIME_APPLE_ID`. Check logs for `contact=`. |
| **US number not working** | 10-digit numbers get `1` prepended automatically. If you set `FACETIME_DEFAULT_COUNTRY_CODE`, it overrides that (e.g. `91` for India). |
| **Vision click never runs** | Ensure Agent-S is up and `AGENT_PORT` matches (e.g. `8005`). Backend will fall back to AppleScript if the vision request fails. |
| **Window shows Mac's email (e.g. punjanianuradha@gmail.com) as target** | Send "FaceTime me" from the number or Apple ID you want to be called at (e.g. your iPhone number in iMessage). |
| **Join from iPhone (same iCloud) but no video** | Ensure we're calling your number/Apple ID, not the Mac's; and that the Call button was clicked so the call is placed. |

---

## Summary

- **By number**: Message from a phone number → we call that number (US 10-digit gets `1`; other countries use `FACETIME_DEFAULT_COUNTRY_CODE` if set).
- **By iCloud email**: Message from an Apple ID email → we call that Apple ID.
- **Who to call**: Sender first; if none (e.g. UI), then `FACETIME_DEFAULT_NUMBER` or `FACETIME_APPLE_ID`.
- **Clicking Call**: Vision (Agent-S) first, then AppleScript; grant Accessibility for the fallback.
