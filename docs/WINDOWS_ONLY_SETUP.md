# Windows-Only Setup: Control Your PC from Messages

This guide makes the project **fully Windows-specific**: control your PC via **Discord**, **Slack**, or **WhatsApp** messages. **Only your messages** are processed—everyone else is ignored.

---

## What You Get

| Mac Feature | Windows Equivalent |
|-------------|--------------------|
| **iMessage** | Discord, Slack, WhatsApp |
| **FaceTime voice** | call.py (mic) or Teams/Skype + VB-Audio Cable |
| **FaceTime video** | Webcam in Electron app (vision + voice) |
| **Apple Shortcuts** | PowerShell, Task Scheduler, or just message the bot |
| **screencapture** | mss (already used) |

---

## Allowed User (You Only)

**Only messages from you are processed.** Set your user ID for each platform:

| Platform | Env Var | How to get it |
|----------|---------|---------------|
| **Discord** | `ALLOWED_DISCORD_USER_ID` | Enable Developer Mode → Right-click your avatar → Copy User ID |
| **Slack** | `ALLOWED_SLACK_USER_ID` | Your profile → More → Copy member ID (starts with `U`) |
| **WhatsApp** | `ALLOWED_WHATSAPP_PHONE` | Your phone number with country code, e.g. `+1234567890` |

---

## Quick Start: Discord

1. **Create a Discord bot**
   - [Discord Developer Portal](https://discord.com/developers/applications) → New Application → Bot → Copy token
   - OAuth2 → URL Generator → scopes: `bot`, permissions: `Send Messages`, `Read Message History`, `View Channels`
   - Invite the bot to a server or DM it

2. **Get your Discord User ID**
   - Discord Settings → Advanced → Enable Developer Mode
   - Right-click your avatar → Copy User ID

3. **Install and configure**
   ```powershell
   cd backend
   uv add ".[discord]"
   ```
   Add to `.env`:
   ```env
   MESSAGE_SOURCES=discord
   DISCORD_BOT_TOKEN=your-bot-token
   ALLOWED_DISCORD_USER_ID=your-user-id
   ```

4. **DM your bot** – Send: `Open Notepad` (only your messages are processed)

5. **Run** – `.\run_windows.ps1`

---

## Quick Start: Slack

1. **Create a Slack app**
   - [api.slack.com/apps](https://api.slack.com/apps) → Create New App → From scratch
   - **Socket Mode**: Enable (no ngrok needed)
   - **App-Level Token**: Create token with `connections:write`
   - **Bot Token**: OAuth & Permissions → `chat:write`, `channels:history`, `im:history`, `groups:history`
   - Install app to workspace

2. **Get your Slack User ID**
   - Slack → Your profile → More → Copy member ID (e.g. `U01234567`)

3. **Install and configure**
   ```powershell
   cd backend
   uv add ".[slack]"
   ```
   Add to `.env`:
   ```env
   MESSAGE_SOURCES=slack
   SLACK_BOT_TOKEN=xoxb-your-bot-token
   SLACK_APP_TOKEN=xapp-your-app-token
   ALLOWED_SLACK_USER_ID=U01234567
   ```

4. **DM the bot** – Send: `Open Notepad`

5. **Run** – `.\run_windows.ps1`

---

## Quick Start: WhatsApp (Twilio)

1. **Twilio setup**
   - [twilio.com](https://www.twilio.com) → Console → Account SID, Auth Token
   - Messaging → Try it out → Send a WhatsApp message → Get sandbox number

2. **Webhook URL** – Twilio needs a public URL. Use ngrok:
   ```powershell
   ngrok http 8100
   ```
   Set webhook to `https://xxx.ngrok.io/webhooks/whatsapp`

3. **Install and configure**
   ```powershell
   cd backend
   uv add ".[whatsapp]"
   ```
   Add to `.env`:
   ```env
   MESSAGE_SOURCES=whatsapp
   TWILIO_ACCOUNT_SID=your-sid
   TWILIO_AUTH_TOKEN=your-token
   TWILIO_WHATSAPP_NUMBER=whatsapp:+14155238886
   ALLOWED_WHATSAPP_PHONE=+1234567890
   ```

4. **Join Twilio sandbox** – Send the join code to the sandbox number from your WhatsApp

5. **Run** – `.\run_windows.ps1` (with ngrok running)

---

## Contact Link: Message Your PC from Your Phone

Get your contact links (WhatsApp number, Discord bot, Slack) to add to your phone:

```
GET http://localhost:8003/api/contact_links
```

Or open the app and check the Contact section. Add the WhatsApp number to your phone contacts, or DM your Discord/Slack bot. **Only your messages** (via `ALLOWED_*`) are processed.

---

## Browser Tasks (Stagehand)

For Chrome, Google, YouTube, etc., the system uses **Browserbase Stagehand** for accurate browser automation.

**Examples you can text:**
- *"Open Chrome and search Sakshi Tripathy on Google"*
- *"Open Chrome and go to YouTube Music and play some music"*
- *"Go to google.com and search for TreeHacks 2026"*

### Setup

1. **Install Stagehand**
   ```powershell
   cd backend
   uv add ".[stagehand]"
   ```

2. **Add to `.env`**
   ```env
   MODEL_API_KEY=sk-your-openai-key
   # Or use OPENAI_API_KEY
   ```

3. **Local mode** (Chrome on your PC): No extra setup. Chrome must be installed.

4. **Browserbase cloud** (optional): For headless cloud browsers:
   ```env
   STAGEHAND_USE_BROWSERBASE=true
   BROWSERBASE_API_KEY=your-key
   BROWSERBASE_PROJECT_ID=your-project-id
   ```

5. **Run** – `run_windows.ps1` starts the Stagehand service automatically.

---

## Multiple Platforms

Use all three at once:

```env
MESSAGE_SOURCES=discord,slack,whatsapp
ALLOWED_DISCORD_USER_ID=123456789
ALLOWED_SLACK_USER_ID=U01234567
ALLOWED_WHATSAPP_PHONE=+1234567890
# ... plus tokens for each
```

---

## Flow: Message → Windows Action

```
You (Discord/Slack/WhatsApp)  →  "Open Notepad"
        ↓
windows_message_bridge  →  checks ALLOWED_* (only your messages pass)
        ↓
POST /api/new_imessage  →  main.py  →  Agent-S
        ↓
Agent-S  →  LLM + pyautogui  →  opens Notepad
        ↓
POST /api/completetask  →  main.py  →  POST /api/send_imessage
        ↓
windows_message_bridge  →  sends reply to you
```

---

## Video / Voice on Windows

### Option A: Built-in (no extra setup)
- **Voice**: Use the mic button in the Electron app (Web Speech API)
- **Vision**: Use the camera button for hand-gesture cursor control

### Option B: Teams / Skype / Zoom
- Install **VB-Audio Cable** (free virtual audio device)
- Route call audio into the Cable input
- Set `AUDIO_INPUT_DEVICE=VB-Audio Cable` in `.env`
- call.py captures the call audio and forwards to Agent-S

### Option C: Webcam only
- call.py can use your default mic
- Start a call in the app; voice goes through call.py → Agent-S

---

## Environment Variables (Windows)

| Variable | Description |
|----------|-------------|
| `MESSAGE_SOURCES` | Comma-separated: `discord`, `slack`, `whatsapp` |
| `ALLOWED_DISCORD_USER_ID` | Your Discord user ID (only your messages processed) |
| `ALLOWED_SLACK_USER_ID` | Your Slack user ID (e.g. `U01234567`) |
| `ALLOWED_WHATSAPP_PHONE` | Your phone with country code (e.g. `+1234567890`) |
| `DISCORD_BOT_TOKEN` | From Discord Developer Portal |
| `SLACK_BOT_TOKEN` | `xoxb-*` from Slack app |
| `SLACK_APP_TOKEN` | `xapp-*` for Socket Mode |
| `TWILIO_*` | For WhatsApp (Account SID, Auth Token, WhatsApp number) |
| `IMESSAGE_BRIDGE_HOST` | `127.0.0.1` (bridge listens here) |
| `IMESSAGE_BRIDGE_PORT` | `8100` |
| `AUDIO_INPUT_DEVICE` | Optional: e.g. `VB-Audio Cable` for call capture |

---

## Run Order

`run_windows.ps1` starts (in separate windows):

1. **windows_message_bridge.py** – Discord/Slack/WhatsApp → backend
2. **main.py** – HTTP API, routes to Agent-S
3. **Agent-S** – LLM + screen control
4. **call.py** – Voice capture/playback
5. **Frontend** – Electron UI

---

## Troubleshooting

- **"No message sources configured"** – Set `MESSAGE_SOURCES` and the required tokens for each platform
- **Messages ignored** – Check `ALLOWED_*` matches your user ID/phone exactly
- **Discord: "discord.py not installed"** – Run `uv add ".[discord]"` in `backend/`
- **Slack: "slack-bolt not installed"** – Run `uv add ".[slack]"` in `backend/`
- **WhatsApp: webhook not receiving** – Use ngrok, set Twilio webhook to `https://xxx.ngrok.io/webhooks/whatsapp`
- **"Failed to deliver to backend"** – Ensure main.py is running on port 8003
